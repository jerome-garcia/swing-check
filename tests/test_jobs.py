"""Background jobs: finished ones are forgotten after a while."""


def test_finished_jobs_are_forgotten_after_a_while(monkeypatch):
    from swingcheck.app import jobs as jobs_module
    manager = jobs_module.JobManager()
    old = manager.wait(manager.submit("a", "convert", lambda progress: None).id)
    monkeypatch.setattr(jobs_module.time, "time", lambda: old.finished + jobs_module.KEEP_FINISHED_S + 1)
    new = manager.submit("b", "convert", lambda progress: None)
    assert manager.get(old.id) is None and manager.get(new.id) is not None
