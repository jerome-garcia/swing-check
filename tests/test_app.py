import json

import pytest
from fastapi.testclient import TestClient

from swingcheck.app.server import create_app
from swingcheck.app.store import Store, SwingNotFound


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


def test_store_ids_are_unique_and_safe(runs):
    store = Store(runs)
    a = store.create("My Swing (240fps).MOV", "fo")
    b = store.create("My Swing (240fps).MOV", "fo")
    assert a.id != b.id and a.id.endswith("my-swing-240fps")
    assert store.summary(a.id)["status"] == "uploaded"
    with pytest.raises(SwingNotFound):
        store.path("../etc")
