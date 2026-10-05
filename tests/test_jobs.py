"""Background jobs: finished ones are forgotten after a while."""


def test_finished_jobs_are_forgotten_after_a_while(monkeypatch):
    from swingcheck.app import jobs as jobs_module
    manager = jobs_module.JobManager()
    old = manager.wait(manager.submit("a", "convert", lambda progress: None).id)
    monkeypatch.setattr(jobs_module.time, "time", lambda: old.finished + jobs_module.KEEP_FINISHED_S + 1)
    new = manager.submit("b", "convert", lambda progress: None)
    assert manager.get(old.id) is None and manager.get(new.id) is not None


def test_queued_jobs_know_their_place_in_line():
    import threading

    from swingcheck.app.jobs import JobManager
    manager = JobManager()
    release = threading.Event()
    running = manager.submit("a", "analyze", lambda progress: release.wait(5))
    second = manager.submit("b", "analyze", lambda progress: None)
    third = manager.submit("c", "convert", lambda progress: None)
    for _ in range(100):  # until the worker has started the first job
        if manager.get(running.id).state == "running":
            break
        threading.Event().wait(0.02)
    assert manager.get(second.id).ahead == 1
    assert manager.get(second.id).message == "Waiting in line: 1 swing ahead of yours, about 2 min"
    assert manager.get(third.id).ahead == 2 and "2 swings ahead of yours, about 3 min" in manager.get(third.id).message
    assert manager.active_for("c").ahead == 2  # what the swing page polls
    release.set()
    assert manager.wait(third.id).state == "done" and manager.get(third.id).ahead is None
