"""Shared summaries: a link anyone can open to one swing's summary, and nothing else."""

import json

import cv2
import numpy as np
from fastapi.testclient import TestClient

from swingcheck.app.server import create_app
from swingcheck.app.store import Store
from swingcheck.pipeline import save_marks
from tests.helpers import make_info


def analyzed_swing(root, name="Juan dela Cruz swing"):
    """An analyzed down-the-line swing with a key-frame sheet, as a hosted visitor's."""
    store = Store(root)
    meta = store.create(f"{name}.mov", "dtl")
    folder = root / meta.id
    info = make_info()
    info.save(folder / "video.json")
    (folder / "normalized.mp4").write_bytes(b"")
    save_marks(folder, "dtl", 5, {"ball": (1, 2), "clubhead": (3, 4), "grip": (5, 6)}, info)
    (folder / "analysis.json").write_text(json.dumps({"view": "dtl", "verdicts": [
        {"name": "address", "title": "Address posture", "status": "ok", "label": "Good posture", "rows": []},
        {"name": "top", "title": "Top", "status": "flag", "label": "Front arm too steep", "rows": []}]}))
    cv2.imwrite(str(folder / "summary.png"), np.full((640, 1080, 3), 90, np.uint8))
    return meta


def test_share_shows_one_summary_and_stop_sharing_ends_it(tmp_path):
    meta = analyzed_swing(tmp_path)
    owner = TestClient(create_app(tmp_path))
    url = owner.post(f"/api/swings/{meta.id}/share", json={}).json()["url"]
    code = url.rsplit("/", 1)[1]
    assert len(code) >= 20 and meta.id not in url

    visitor = TestClient(create_app(tmp_path))
    page = visitor.get(f"/s/{code}")
    assert page.status_code == 200
    assert "Juan" not in page.text  # never the video's file name
    assert f"/s/{code}/preview.jpg" in page.text and 'property="og:image"' in page.text
    assert "Address" in page.text and "Fix" in page.text and "Front arm too steep" in page.text
    assert "2 checkpoints: 1 good, 0 to watch, and 1 to fix." in page.text
    pdf = visitor.get(f"/s/{code}/summary.pdf")
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf"
    assert pdf.headers["content-disposition"].startswith("inline") and pdf.content.startswith(b"%PDF")
    assert visitor.get(f"/s/{code}/preview.jpg").headers["content-type"] == "image/jpeg"

    # Sharing again keeps the link; stop sharing ends it at once.
    assert owner.post(f"/api/swings/{meta.id}/share", json={}).json()["url"] == url
    assert owner.delete(f"/api/swings/{meta.id}/share").status_code == 200
    for path in (f"/s/{code}", f"/s/{code}/summary.pdf", f"/s/{code}/preview.jpg"):
        assert visitor.get(path).status_code == 404
    assert not (tmp_path / meta.id / "shared-summary.pdf").exists()
    assert visitor.get("/s/not-a-real-code").status_code == 404


def test_hosted_share_link_works_for_anyone_but_the_swing_stays_private(tmp_path):
    owner = TestClient(create_app(tmp_path, hosted=True))
    owner.get("/")  # gets an owner key
    from swingcheck.app.hosted import owner_of
    meta = analyzed_swing(tmp_path)
    meta.owner = owner_of(owner.cookies.get("swingcheck_owner"))
    Store(tmp_path).save_meta(meta)
    r = owner.post(f"/api/swings/{meta.id}/share", json={})
    assert r.status_code == 200 and r.json()["url"].startswith("https://")
    code = r.json()["url"].rsplit("/", 1)[1]

    stranger = TestClient(create_app(tmp_path, hosted=True))
    assert stranger.get(f"/s/{code}").status_code == 200
    assert "Link works until" in stranger.get(f"/s/{code}").text
    assert stranger.get(f"/api/swings/{meta.id}").status_code == 404  # the swing itself: still private
    assert stranger.post(f"/api/swings/{meta.id}/share", json={}).status_code == 404
    assert stranger.delete(f"/api/swings/{meta.id}/share").status_code == 404


def test_only_analyzed_swings_can_be_shared(tmp_path):
    meta = analyzed_swing(tmp_path)
    (tmp_path / meta.id / "analysis.json").unlink()
    assert TestClient(create_app(tmp_path)).post(f"/api/swings/{meta.id}/share", json={}).status_code == 409
