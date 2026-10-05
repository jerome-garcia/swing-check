"""Background jobs (convert, analyze) run one at a time on a worker thread.

Pose tracking uses the whole CPU, so running jobs in parallel wouldn't make
anything faster. The page polls a job for its stage, progress and result.
"""

from __future__ import annotations

import queue
import threading
import time
import traceback
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any

# A job function receives a progress callback: progress(stage, fraction, message).
JobFn = Callable[[Callable[[str, float | None, str], None]], Any]

# Finished jobs are forgotten after this long, so a server that runs for months doesn't
# keep every job ever. The swing page only needs a job while it runs, and a failed one
# for its error message, which is read soon after.
KEEP_FINISHED_S = 6 * 60 * 60

# Rough time per job on the 2-CPU server, for the "N ahead of yours, about M min" message.
TYPICAL_S = {"convert": 20, "analyze": 90}


@dataclass
class Job:
    id: str
    swing_id: str
    kind: str  # "convert" | "analyze"
    state: str = "queued"  # queued | running | done | failed
    stage: str = ""
    fraction: float | None = None
    message: str = "Waiting for another job to finish"
    ahead: int | None = None  # while queued: jobs running or queued before this one
    error: str | None = None
    created: float = field(default_factory=time.time)
    started: float | None = None
    finished: float | None = None

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


class JobManager:
    def __init__(self, on_finish: Callable[[Job], None] | None = None) -> None:
        # Called with each job once it's done or failed (the admin page's event log).
        self._on_finish = on_finish
        self._jobs: dict[str, Job] = {}
        self._fns: dict[str, JobFn] = {}
        self._queue: queue.Queue[str] = queue.Queue()
        self._lock = threading.Lock()
        self._worker = threading.Thread(target=self._run, name="swingcheck-jobs", daemon=True)
        self._worker.start()

    def submit(self, swing_id: str, kind: str, fn: JobFn) -> Job:
        job = Job(id=uuid.uuid4().hex[:12], swing_id=swing_id, kind=kind)
        with self._lock:
            self._forget_old(time.time())
            self._jobs[job.id] = job
            self._fns[job.id] = fn
        self._queue.put(job.id)
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._placed(self._jobs.get(job_id))

    def active_for(self, swing_id: str) -> Job | None:
        """The queued or running job for a swing, if any."""
        with self._lock:
            for job in self._jobs.values():
                if job.swing_id == swing_id and job.state in ("queued", "running"):
                    return self._placed(job)
        return None

    def snapshot(self) -> list[Job]:
        """Copies of the queued and running jobs, in the order they run (admin page)."""
        with self._lock:
            return [Job(**asdict(j)) for j in self._jobs.values() if j.state in ("queued", "running")]

    def pending(self) -> int:
        """How many jobs are queued or running."""
        with self._lock:
            return sum(job.state in ("queued", "running") for job in self._jobs.values())

    def latest_for(self, swing_id: str) -> Job | None:
        with self._lock:
            jobs = [j for j in self._jobs.values() if j.swing_id == swing_id]
            return self._placed(max(jobs, key=lambda j: j.created)) if jobs else None

    def _placed(self, job: Job | None) -> Job | None:
        """A queued job with its place in line and a rough wait (call with the lock held)."""
        if job is None or job.state != "queued":
            return job
        # Jobs are kept in the order they were submitted, which is the order they run.
        order = list(self._jobs)
        mine = order.index(job.id)
        before = [j for i, j in enumerate(self._jobs.values())
                  if j.state == "running" or (j.state == "queued" and i < mine)]
        job.ahead = len(before)
        if before:
            minutes = max(1, round(sum(TYPICAL_S.get(j.kind, 60) for j in before) / 60))
            job.message = (f"Waiting in line: {len(before)} {'swing' if len(before) == 1 else 'swings'} "
                           f"ahead of yours, about {minutes} min")
        else:
            job.message = "Starting soon"
        return job

    def _forget_old(self, now: float) -> None:
        """Drop jobs that finished more than KEEP_FINISHED_S ago (call with the lock held)."""
        for job_id in [j.id for j in self._jobs.values() if j.finished and now - j.finished > KEEP_FINISHED_S]:
            del self._jobs[job_id]

    def wait(self, job_id: str, timeout: float = 600) -> Job:
        """Block until a job finishes (for tests)."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            job = self.get(job_id)
            if job and job.state in ("done", "failed"):
                return job
            time.sleep(0.05)
        raise TimeoutError(job_id)

    def _run(self) -> None:
        while True:
            job_id = self._queue.get()
            with self._lock:
                job, fn = self._jobs[job_id], self._fns.pop(job_id)
                job.state, job.message, job.ahead = "running", "Starting", None
                job.started = time.time()

            def progress(stage: str, fraction: float | None, message: str, job: Job = job) -> None:
                with self._lock:
                    job.stage, job.fraction, job.message = stage, fraction, message

            try:
                fn(progress)
                with self._lock:
                    job.state, job.fraction, job.message = "done", 1.0, "Done"
                    job.finished = time.time()
            except Exception as e:  # noqa: BLE001 - report any failure to the page
                with self._lock:
                    job.state = "failed"
                    job.error = str(e) or e.__class__.__name__
                    job.message = "Failed"
                    job.finished = time.time()
                traceback.print_exc()
            if self._on_finish:
                try:
                    self._on_finish(job)
                except Exception:  # noqa: BLE001 - stats must never break the queue
                    traceback.print_exc()
