import json
import shutil

import numpy as np
import pytest
from fastapi.testclient import TestClient

from swingcheck.app.server import create_app
from swingcheck.app.store import Store, SwingNotFound
from swingcheck.output.video import VideoWriter


@pytest.fixture
def runs(tmp_path):
    root = tmp_path / "runs"
    root.mkdir()
    # A pre-app run folder: analyzed DTL swing without swing.json.
    old = root / "old_swing"
    old.mkdir()
    (old / "marks.json").write_text(json.dumps({"view": "dtl"}))
    (old / "analysis.json").write_text(json.dumps({"view": "dtl", "verdicts": [
        {"title": "Address posture", "status": "ok", "label": "good"}]}))
    (old / "address.png").write_bytes(b"png")
    return root


@pytest.fixture
def client(runs):
    return TestClient(create_app(runs))


def test_lists_existing_runs(client):
    swings = client.get("/api/swings").json()
    assert len(swings) == 1
    s = swings[0]
    assert s["id"] == "old_swing" and s["name"] == "old swing"
    assert s["view"] == "dtl" and s["status"] == "analyzed"
    assert s["verdicts"] == [{"title": "Address posture", "status": "ok", "label": "good"}]
    assert s["thumbnail"] == "address.png"


def test_detail_and_files(client):
    d = client.get("/api/swings/old_swing").json()
    assert d["analysis"]["view"] == "dtl" and d["video"] is None
    assert "address.png" in d["files"]
    assert client.get("/files/old_swing/address.png").content == b"png"


def test_unknown_and_unsafe_paths_404(client):
    assert client.get("/api/swings/nope").status_code == 404
    assert client.get("/files/old_swing/..%2F..%2Fsecret.txt").status_code == 404
    assert client.get("/files/old_swing/marks.json").status_code == 200  # inside the folder is fine


def test_delete(client, runs):
    assert client.delete("/api/swings/old_swing").status_code == 200
    assert not (runs / "old_swing").exists()
    assert client.get("/api/swings").json() == []


def test_frontend_served(client):
    r = client.get("/")
    assert r.status_code == 200 and "swing-check" in r.text


def test_upload_rejects_non_video_and_bad_view(client):
    r = client.post("/api/swings", files={"file": ("notes.txt", b"hi")}, data={"view": "dtl"})
    assert r.status_code == 400 and "video" in r.json()["detail"]
    r = client.post("/api/swings", files={"file": ("a.mov", b"x")}, data={"view": "side"})
    assert r.status_code == 400


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not on PATH")
def test_upload_converts_in_background(client, tmp_path):
    clip = tmp_path / "My Swing.mp4"
    with VideoWriter(clip, 64, 96, 30.0) as w:
        for i in range(30):
            w.write(np.full((96, 64, 3), i * 8, np.uint8))
    with open(clip, "rb") as f:
        r = client.post("/api/swings", files={"file": ("My Swing.mp4", f, "video/mp4")}, data={"view": "fo"})
    assert r.status_code == 200
    swing_id, job_id = r.json()["id"], r.json()["job"]["id"]
    job = client.app.state.jobs.wait(job_id, timeout=60)
    assert job.state == "done", job.error
    d = client.get(f"/api/swings/{swing_id}").json()
    assert d["status"] == "converted" and d["view"] == "fo" and d["name"] == "My Swing"
    assert d["video"]["frame_count"] == 30
    assert d["job"]["state"] == "done"


def test_broken_video_conversion_fails_cleanly(client):
    r = client.post("/api/swings", files={"file": ("broken.mov", b"not really a video")}, data={"view": "dtl"})
    job = client.app.state.jobs.wait(r.json()["job"]["id"], timeout=60)
    assert job.state == "failed" and job.error
    d = client.get(f"/api/swings/{r.json()['id']}").json()
    assert d["status"] == "uploaded" and d["job"]["state"] == "failed"


def test_store_ids_are_unique_and_safe(runs):
    store = Store(runs)
    a = store.create("My Swing (240fps).MOV", "fo")
    b = store.create("My Swing (240fps).MOV", "fo")
    assert a.id != b.id and a.id.endswith("my-swing-240fps")
    assert store.summary(a.id)["status"] == "uploaded"
    with pytest.raises(SwingNotFound):
        store.path("../etc")
