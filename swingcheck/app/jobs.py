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


@dataclass
class Job:
    id: str
    swing_id: str
    kind: str  # "convert" | "analyze"
    state: str = "queued"  # queued | running | done | failed
    stage: str = ""
    fraction: float | None = None
    message: str = "Waiting for another job to finish"
    error: str | None = None
    created: float = field(default_factory=time.time)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._fns: dict[str, JobFn] = {}
        self._queue: queue.Queue[str] = queue.Queue()
        self._lock = threading.Lock()
        self._worker = threading.Thread(target=self._run, name="swingcheck-jobs", daemon=True)
        self._worker.start()

    def submit(self, swing_id: str, kind: str, fn: JobFn) -> Job:
        job = Job(id=uuid.uuid4().hex[:12], swing_id=swing_id, kind=kind)
        with self._lock:
            self._jobs[job.id] = job
            self._fns[job.id] = fn
        self._queue.put(job.id)
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def active_for(self, swing_id: str) -> Job | None:
        """The queued or running job for a swing, if any."""
        with self._lock:
            for job in self._jobs.values():
                if job.swing_id == swing_id and job.state in ("queued", "running"):
                    return job
        return None

    def pending(self) -> int:
        """How many jobs are queued or running."""
        with self._lock:
            return sum(job.state in ("queued", "running") for job in self._jobs.values())

    def latest_for(self, swing_id: str) -> Job | None:
        with self._lock:
            jobs = [j for j in self._jobs.values() if j.swing_id == swing_id]
        return max(jobs, key=lambda j: j.created) if jobs else None

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
                job.state, job.message = "running", "Starting"

            def progress(stage: str, fraction: float | None, message: str, job: Job = job) -> None:
                with self._lock:
                    job.stage, job.fraction, job.message = stage, fraction, message

            try:
                fn(progress)
                with self._lock:
                    job.state, job.fraction, job.message = "done", 1.0, "Done"
            except Exception as e:  # noqa: BLE001 - report any failure to the page
                with self._lock:
                    job.state = "failed"
                    job.error = str(e) or e.__class__.__name__
                    job.message = "Failed"
                traceback.print_exc()
