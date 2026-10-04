import json
import shutil

import numpy as np
import pytest
from fastapi.testclient import TestClient

from swingcheck.app import server
from swingcheck.app.server import create_app
from swingcheck.app.store import Store, SwingNotFound
from swingcheck.output.video import VideoWriter
from swingcheck.pipeline import save_marks
from tests.helpers import make_info


DTL_POINTS = {"ball": [30, 80], "clubhead": [28, 82], "grip": [20, 50]}


@pytest.fixture
def runs(tmp_path):
    root = tmp_path / "runs"
    root.mkdir()
    # A pre-app run folder: analyzed DTL swing without swing.json.
    old = root / "old_swing"
    old.mkdir()
    info = make_info()
    info.save(old / "video.json")
    (old / "normalized.mp4").write_bytes(b"")
    save_marks(old, "dtl", 5, {"ball": (1, 2), "clubhead": (3, 4), "grip": (5, 6)}, info)
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
    assert s["verdicts"] == [{"name": None, "title": "Address posture", "status": "ok", "label": "good"}]
    assert s["thumbnail"] == "address.png"


def test_detail_and_files(client):
    d = client.get("/api/swings/old_swing").json()
    assert d["analysis"]["view"] == "dtl" and d["video"]["fps"] == 240.0
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
        r = client.post("/api/swings", files={"file": ("My Swing.mp4", f, "video/mp4")}, data={"view": "dtl"})
    assert r.status_code == 200
    swing_id, job_id = r.json()["id"], r.json()["job"]["id"]
    job = client.app.state.jobs.wait(job_id, timeout=60)
    assert job.state == "done", job.error
    d = client.get(f"/api/swings/{swing_id}").json()
    assert d["status"] == "converted" and d["view"] == "dtl" and d["name"] == "My Swing"
    assert d["video"]["frame_count"] == 30
    assert d["job"]["state"] == "done"


@pytest.fixture
def converted(client, tmp_path):
    """A 1-second 30fps down-the-line clip, uploaded and converted. Returns its swing id."""
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not on PATH")
    clip = tmp_path / "clip.mp4"
    with VideoWriter(clip, 64, 96, 30.0) as w:
        for i in range(30):
            w.write(np.full((96, 64, 3), i * 8, np.uint8))
    with open(clip, "rb") as f:
        r = client.post("/api/swings", files={"file": ("clip.mp4", f)}, data={"view": "dtl"})
    assert client.app.state.jobs.wait(r.json()["job"]["id"], timeout=60).state == "done"
    return r.json()["id"]


def test_frame_images(client, converted):
    r = client.get(f"/api/swings/{converted}/frames/5.jpg")
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    assert r.content[:2] == b"\xff\xd8"
    assert client.get(f"/api/swings/{converted}/frames/9999.jpg").status_code == 404


def test_save_marks_moves_swing_to_marked(client, converted):
    r = client.post(f"/api/swings/{converted}/marks", json={"address_frame": 3, "points": {"ball": [30, 80]}})
    assert r.status_code == 400 and "clubhead" in r.json()["detail"]
    r = client.post(f"/api/swings/{converted}/marks", json={"address_frame": 3, "points": DTL_POINTS})
    assert r.status_code == 200
    d = client.get(f"/api/swings/{converted}").json()
    assert d["status"] == "marked" and d["marks"]["address_frame"] == 3


def test_trim_reconverts_and_invalidates_marks(client, converted):
    client.post(f"/api/swings/{converted}/marks", json={"address_frame": 3, "points": DTL_POINTS})
    assert client.post(f"/api/swings/{converted}/trim", json={"start": 0.5, "end": 0.2}).status_code == 400
    r = client.post(f"/api/swings/{converted}/trim", json={"start": 0.5, "end": None})
    assert r.status_code == 200
    assert client.app.state.jobs.wait(r.json()["job"]["id"], timeout=60).state == "done"
    d = client.get(f"/api/swings/{converted}").json()
    assert d["video"]["trim_start"] == 0.5 and d["video"]["frame_count"] == 15
    assert d["status"] == "converted"  # old marks were for the untrimmed clip


def test_checkpoint_list_marks_built_ones(client):
    cps = client.get("/api/features").json()["checkpoints"]["dtl"]
    assert [c["number"] for c in cps] == list(range(1, 9))
    built = {c["analyzer"] for c in cps if c["built"]}
    assert built == {"address", "swing_plane", "takeaway", "halfway_back", "top", "downswing", "impact", "follow_through"}  # update as checkpoints land
    assert cps[0]["title"] == "Address" and cps[0]["phase"] == "address"


def test_face_on_held_back_for_future_release(client, runs):
    assert client.get("/api/features").json()["face_on"] is False
    r = client.post("/api/swings", files={"file": ("a.mov", b"x")}, data={"view": "fo"})
    assert r.status_code == 400 and "future release" in r.json()["detail"]
    assert client.post("/api/swings/old_swing/view", json={"view": "fo"}).status_code == 400
    assert not list(runs.glob("*-a"))  # nothing was created


def test_change_view_requires_marking_again(client, runs, monkeypatch):
    monkeypatch.setattr(server, "FACE_ON_ENABLED", True)
    assert client.get("/api/swings/old_swing").json()["status"] == "analyzed"
    assert client.post("/api/swings/old_swing/view", json={"view": "side"}).status_code == 400
    r = client.post("/api/swings/old_swing/view", json={"view": "fo"})
    assert r.status_code == 200 and r.json()["view"] == "fo"
    assert r.json()["status"] == "converted"  # its marks were for down-the-line
    assert json.loads((runs / "old_swing" / "swing.json").read_text())["view"] == "fo"


def test_analyze_requires_marks(client, converted):
    r = client.post(f"/api/swings/{converted}/analyze", json={})
    assert r.status_code == 409 and "Mark" in r.json()["detail"]


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
