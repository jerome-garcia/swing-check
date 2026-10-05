"""Hosted mode: visitors kept apart by an owner-key cookie, with swing limits and expiry."""

import json
import shutil
from datetime import datetime, timedelta

import numpy as np
import pytest
from fastapi.testclient import TestClient

from swingcheck.app.hosted import OWNER_COOKIE, sweep
from swingcheck.app.server import create_app
from swingcheck.output.video import VideoWriter


@pytest.fixture
def app(tmp_path):
    runs = tmp_path / "runs"
    runs.mkdir()
    legacy = runs / "old_swing"  # someone's swing from before hosting: nobody owns it
    legacy.mkdir()
    (legacy / "address.png").write_bytes(b"png")
    return create_app(runs, hosted=True)


@pytest.fixture
def alice(app):
    return TestClient(app)


@pytest.fixture
def bob(app):
    return TestClient(app)


def upload(client, name="swing.mov", data=b"not really a video"):
    """Upload a clip and let its conversion finish (a fake clip just fails to convert)."""
    r = client.post("/api/swings", files={"file": (name, data)}, data={"view": "dtl", "agreed_terms": "2026-10-05"})
    if r.status_code == 200:
        client.app.state.jobs.wait(r.json()["job"]["id"], timeout=60)
    return r


def test_each_visitor_sees_only_their_own_swings(alice, bob):
    r = upload(alice)
    assert r.status_code == 200
    swing_id, job_id = r.json()["id"], r.json()["job"]["id"]
    assert len(swing_id) == 32 and "swing" not in swing_id  # random, not date + name

    mine = alice.get("/api/swings").json()
    assert [s["id"] for s in mine] == [swing_id] and "owner" not in mine[0]
    assert mine[0]["expires"]
    assert alice.get(f"/api/swings/{swing_id}").status_code == 200

    assert bob.get("/api/swings").json() == []  # not alice's, and not the unowned old swing
    for path in (f"/api/swings/{swing_id}", f"/api/swings/{swing_id}/frames/0.jpg", f"/files/{swing_id}/swing.json",
                 f"/api/swings/{swing_id}/summary.pdf", f"/api/jobs/{job_id}", "/api/swings/old_swing",
                 "/files/old_swing/address.png"):
        assert bob.get(path).status_code == 404, path
    assert bob.post(f"/api/swings/{swing_id}/analyze", json={}).status_code == 404
    assert bob.delete(f"/api/swings/{swing_id}").status_code == 404
    assert alice.get(f"/api/swings/{swing_id}").status_code == 200  # still there


def test_upload_needs_agreement_to_the_terms(alice, app):
    r = alice.post("/api/swings", files={"file": ("a.mov", b"x")}, data={"view": "dtl"})
    assert r.status_code == 400 and "Terms" in r.json()["detail"]
    swing_id = upload(alice).json()["id"]
    notes = json.loads((app.state.store.path(swing_id) / "swing.json").read_text())["notes"]
    assert notes["agreed_terms"]["version"] == "2026-10-05" and notes["agreed_terms"]["at"]


def test_owner_cookie_and_no_indexing(alice):
    r = alice.get("/")
    cookie = r.headers["set-cookie"]
    assert cookie.startswith(f"{OWNER_COOKIE}=") and "HttpOnly" in cookie and "SameSite=lax" in cookie
    assert r.headers["x-robots-tag"] == "noindex, nofollow"
    assert "set-cookie" not in alice.get("/").headers  # kept, not replaced


def test_swing_folder_stores_a_hash_not_the_key(alice, app):
    swing_id = upload(alice).json()["id"]
    key = alice.get("/api/owner").json()["key"]
    stored = json.loads((app.state.store.path(swing_id) / "swing.json").read_text())
    assert stored["owner"] and key not in stored["owner"]


def test_swing_limit_then_delete_one_to_add_another(alice, bob, app):
    limit = app.state.config["hosted"]["max_swings"]
    ids = [upload(alice).json()["id"] for _ in range(limit)]
    r = upload(alice)
    assert r.status_code == 409 and "Delete one" in r.json()["detail"]
    assert alice.get("/api/owner").json()["swings"] == limit
    assert upload(bob).status_code == 200  # the limit is per visitor
    assert alice.delete(f"/api/swings/{ids[0]}").status_code == 200
    assert upload(alice).status_code == 200


def test_private_link_opens_the_same_swings_elsewhere(alice, bob):
    swing_id = upload(alice).json()["id"]
    key = alice.get("/api/owner").json()["key"]
    assert bob.post("/api/owner/claim", json={"key": "nope"}).status_code == 400
    r = bob.post("/api/owner/claim", json={"key": key})
    assert r.status_code == 200 and r.json() == {"swings": 1}
    assert f"{OWNER_COOKIE}={key}" in r.headers["set-cookie"]
    assert [s["id"] for s in bob.get("/api/swings").json()] == [swing_id]


def test_swings_expire_after_keep_days(alice, app):
    swing_id = upload(alice).json()["id"]
    store, jobs = app.state.store, app.state.jobs
    assert sweep(store, jobs, 3, now=datetime.now() + timedelta(days=2)) == []
    assert swing_id in sweep(store, jobs, 3, now=datetime.now() + timedelta(days=3, minutes=1))
    assert alice.get("/api/swings").json() == []


def test_upload_limits(alice, app):
    limits = app.state.config["hosted"]
    limits["max_upload_mb"] = 0.00001
    r = upload(alice)
    assert r.status_code == 413 and "MB" in r.json()["detail"]
    limits["max_upload_mb"] = 200
    limits["max_queued_jobs"] = 0
    r = upload(alice)
    assert r.status_code == 503 and "busy" in r.json()["detail"]
    assert alice.get("/api/swings").json() == []


def test_uploads_per_ip_per_day(alice, bob, app):
    app.state.config["hosted"]["max_uploads_per_ip_per_day"] = 2
    swing_id = upload(alice).json()["id"]
    assert upload(bob).status_code == 200
    r = upload(alice)  # same address (the test client), under alice's swing limit
    assert r.status_code == 429 and "tomorrow" in r.json()["detail"]
    alice.delete(f"/api/swings/{swing_id}")
    assert upload(alice).status_code == 429  # deleting doesn't give uploads back


def test_upload_counter_forgets_after_a_day():
    from swingcheck.app.hosted import UploadCounter
    c = UploadCounter()
    c.record("1.2.3.4", now=1000.0)
    c.record("1.2.3.4", now=2000.0)
    assert c.count("1.2.3.4", now=3000.0) == 2
    assert c.count("1.2.3.4", now=1000.0 + UploadCounter.WINDOW_S + 1) == 1
    assert c.count("1.2.3.4", now=2000.0 + UploadCounter.WINDOW_S + 1) == 0
    assert c.count("5.6.7.8") == 0


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not on PATH")
def test_long_clips_are_refused(alice, app, tmp_path):
    app.state.config["hosted"]["max_clip_seconds"] = 0.5
    clip = tmp_path / "long.mp4"
    with VideoWriter(clip, 64, 96, 30.0) as w:
        for i in range(30):  # 1 second
            w.write(np.full((96, 64, 3), i * 8, np.uint8))
    r = upload(alice, "long.mp4", clip.read_bytes())
    assert r.status_code == 400 and "limit is 0.5" in r.json()["detail"]
    assert alice.get("/api/swings").json() == [] and len(list(app.state.store.root.iterdir())) == 1


def test_local_mode_has_no_owners(tmp_path):
    client = TestClient(create_app(tmp_path / "runs"))
    assert client.get("/api/features").json()["hosted"] is None
    assert client.get("/api/owner").status_code == 404
    assert "set-cookie" not in client.get("/").headers
