import json
import shutil
import subprocess

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


def test_health_reports_jobs_and_version(client):
    health = client.get("/api/health").json()
    assert health["ok"] is True and health["jobs"] == 0 and health["uploads"] == 0
    assert health["version"] and health["version"] == client.get("/api/features").json()["version"]


def test_page_addresses_its_css_and_js_by_fingerprint(client):
    for path in ("/", "/index.html"):
        res = client.get(path)
        assert res.status_code == 200 and res.headers["cache-control"] == "no-cache"
        html = res.text
        digest = html.split('href="/style.css?v=')[1].split('"')[0]
        assert len(digest) == 12 and f'src="/app.js?v={digest}"' in html
        imports = json.loads(html.split('<script type="importmap">')[1].split("</script>")[0])["imports"]
        assert imports["/util.js"] == f"/util.js?v={digest}" and "/mark.js" in imports
        assert html.index("importmap") < html.index('type="module"')  # the map must come first
    assert "brand-version" in client.get(f"/style.css?v={digest}").text  # the query doesn't matter to the server


def test_clean_page_addresses_get_the_app(client):
    home = client.get("/").text
    for path in ("/new", "/terms", "/privacy", "/feedback", "/swing/anything", "/swing/anything/mark"):
        res = client.get(path)
        assert res.status_code == 200 and res.text == home, path
    assert client.get("/swing/a/b/c").status_code == 404  # not a page
    assert client.get("/reference/reference.json").status_code == 200  # absolute: works from any page


def test_link_preview_tags_and_image(client):
    html = client.get("/").text
    assert 'property="og:image" content="https://swingcheck.org/og-image.jpg"' in html
    assert 'property="og:title"' in html and 'name="twitter:card"' in html
    image = client.get("/og-image.jpg")
    assert image.status_code == 200 and image.headers["content-type"] == "image/jpeg"
    # Phones building previews themselves (encrypted Messenger chats, WhatsApp) skip big images.
    assert len(image.content) < 250 * 1024


def test_fingerprint_changes_with_the_files(tmp_path, monkeypatch):
    for f in server.STATIC.iterdir():
        if f.is_file():
            shutil.copy(f, tmp_path / f.name)
    monkeypatch.setattr(server, "STATIC", tmp_path)
    before = server.index_page()
    (tmp_path / "util.js").write_text((tmp_path / "util.js").read_text(encoding="utf-8") + "\n// changed\n", encoding="utf-8")
    after = server.index_page()
    assert before != after and before.split("?v=")[1][:12] != after.split("?v=")[1][:12]


def test_health_counts_uploads_in_progress(client, monkeypatch):
    seen = []
    real_create = client.app.state.store.create

    def create(*args, **kwargs):  # runs while the upload request is in progress
        seen.append(client.get("/api/health").json()["uploads"])
        return real_create(*args, **kwargs)

    monkeypatch.setattr(client.app.state.store, "create", create)
    client.post("/api/swings", files={"file": ("clip.mp4", b"not really a video")}, data={"view": "dtl"})
    assert seen == [1] and client.get("/api/health").json()["uploads"] == 0


def test_version_falls_back_to_the_package(monkeypatch):
    def no_git(*args, **kwargs):
        raise FileNotFoundError("git")
    monkeypatch.setattr(server.subprocess, "run", no_git)
    assert server.app_version().startswith("v")


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


def test_summary_pdf_download(client, runs):
    r = client.get("/api/swings/old_swing/summary.pdf")
    assert r.status_code == 200 and r.content.startswith(b"%PDF")
    assert r.headers["content-type"] == "application/pdf"
    assert 'filename="old-swing-summary.pdf"' in r.headers["content-disposition"]
    (runs / "old_swing" / "analysis.json").unlink()
    assert client.get("/api/swings/old_swing/summary.pdf").status_code == 409


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
    assert r.status_code == 200 and "SwingCheck" in r.text


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


def test_frames_cache_only_for_this_conversion(client, converted):
    token = client.get(f"/api/swings/{converted}").json()["video"]["version"]
    assert token
    url = f"/api/swings/{converted}/frames/5.jpg"
    assert client.get(url).headers["cache-control"] == "no-store"  # no token: as before
    cached = client.get(f"{url}?c={token}").headers["cache-control"]
    assert "max-age" in cached and "private" in cached  # private: never kept by Cloudflare
    assert client.get(f"{url}?c=stale").headers["cache-control"] == "no-store"  # an older conversion


def test_conversion_has_short_keyframe_intervals(client, converted):
    folder = client.app.state.store.path(converted)
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "packet=flags",
                          "-of", "csv", str(folder / "normalized.mp4")], capture_output=True, text=True, check=True)
    flags = out.stdout.split()
    assert len(flags) == 30 and sum("K" in f for f in flags) >= 2  # x264's default would be 1 for 30 frames


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


def test_marking_reference_is_bundled(client):
    ref = client.get("/reference/reference.json").json()
    assert ref["name"] == "Rory McIlroy"
    assert list(ref["steps"]) == ["address", "takeaway", "halfway_back", "top", "downswing", "follow_through"]
    for step in ref["steps"].values():
        assert client.get(f"/reference/{step['image']}").content[:2] == b"\xff\xd8"
        assert all(0 <= x <= ref["width"] and 0 <= y <= ref["height"] for x, y in step["points"].values())


def test_detail_includes_suggested_frames_for_this_video(client, runs):
    from swingcheck.ingest import VideoInfo
    from swingcheck.pipeline import SUGGEST_FILE, video_signature

    folder = runs / "old_swing"
    assert client.get("/api/swings/old_swing").json()["suggested"] is None
    sig = video_signature(VideoInfo.load(folder / "video.json"))
    (folder / SUGGEST_FILE).write_text(json.dumps({"video_signature": sig, "phases": {"address": 3, "top": 50}}))
    assert client.get("/api/swings/old_swing").json()["suggested"] == {"address": 3, "top": 50}
    (folder / SUGGEST_FILE).write_text(json.dumps({"video_signature": {**sig, "frame_count": 1}, "phases": {"top": 50}}))
    assert client.get("/api/swings/old_swing").json()["suggested"] is None


def test_conversion_lost_to_a_restart_can_run_again(client, runs):
    # Uploaded, but the app restarted before converting: no job on record.
    meta = client.app.state.store.create("clip.mov", "dtl")
    meta.source_file = "source.mov"
    (runs / meta.id / "source.mov").write_bytes(b"not really a video")
    client.app.state.store.save_meta(meta)
    d = client.get(f"/api/swings/{meta.id}").json()
    assert d["status"] == "uploaded" and d["job"] is None
    r = client.post(f"/api/swings/{meta.id}/trim", json={"start": None, "end": None})
    assert r.status_code == 200 and r.json()["job"]["kind"] == "convert"
    client.app.state.jobs.wait(r.json()["job"]["id"], timeout=60)  # don't leave it running at exit


def test_handedness_is_per_swing_and_switching_it_asks_for_a_new_analysis(client, runs):
    d = client.get("/api/swings/old_swing").json()
    assert d["handedness"] == "right" and d["status"] == "analyzed"  # older swings: right-handed
    assert client.post("/api/swings/old_swing/handedness", json={"handedness": "both"}).status_code == 400
    r = client.post("/api/swings/old_swing/handedness", json={"handedness": "left"})
    assert r.status_code == 200 and r.json()["handedness"] == "left"
    assert r.json()["status"] == "marked"  # marks kept; the right-handed analysis no longer counts
    r = client.post("/api/swings", files={"file": ("a.mov", b"x")}, data={"view": "dtl", "handedness": "left"})
    assert client.get(f"/api/swings/{r.json()['id']}").json()["handedness"] == "left"
    client.app.state.jobs.wait(r.json()["job"]["id"], timeout=60)
    r = client.post("/api/swings", files={"file": ("a.mov", b"x")}, data={"view": "dtl", "handedness": "up"})
    assert r.status_code == 400


def test_club_is_per_swing_and_switching_it_asks_for_a_new_analysis(client, runs):
    d = client.get("/api/swings/old_swing").json()
    assert d["club"] == "iron" and d["status"] == "analyzed"  # older swings: irons
    assert client.post("/api/swings/old_swing/club", json={"club": "putter"}).status_code == 400
    r = client.post("/api/swings/old_swing/club", json={"club": "driver"})
    assert r.status_code == 200 and r.json()["club"] == "driver"
    assert r.json()["status"] == "marked"  # marks kept; the iron analysis no longer counts
    r = client.post("/api/swings", files={"file": ("a.mov", b"x")}, data={"view": "dtl", "club": "driver"})
    assert client.get(f"/api/swings/{r.json()['id']}").json()["club"] == "driver"
    client.app.state.jobs.wait(r.json()["job"]["id"], timeout=60)
    assert client.post("/api/swings", files={"file": ("a.mov", b"x")}, data={"view": "dtl", "club": "putter"}).status_code == 400


def test_key_frames_are_shown_as_small_cached_jpegs(tmp_path):
    import cv2
    import numpy as np

    client = TestClient(create_app(tmp_path))
    meta = client.app.state.store.create("swing.mp4", "dtl")
    folder = tmp_path / meta.id
    cv2.imwrite(str(folder / "check_top.png"), np.random.default_rng(0).integers(0, 255, (1920, 1080, 3), np.uint8))
    r = client.get(f"/files/{meta.id}/check_top.jpg?w=720")
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    assert r.headers["cache-control"] == "no-cache" and r.headers.get("etag")
    assert cv2.imdecode(np.frombuffer(r.content, np.uint8), cv2.IMREAD_COLOR).shape[:2] == (1280, 720)
    small = client.get(f"/files/{meta.id}/check_top.jpg?w=360").content
    assert cv2.imdecode(np.frombuffer(small, np.uint8), cv2.IMREAD_COLOR).shape[1] == 360
    # Unchanged: the browser's copy is still good. Re-analyzed (a newer PNG): a new picture.
    assert client.get(f"/files/{meta.id}/check_top.jpg?w=720", headers={"if-none-match": r.headers["etag"]}).status_code == 304
    import os
    import time
    later = time.time_ns() + 10**9
    os.utime(folder / "check_top.png", ns=(later, later))
    assert client.get(f"/files/{meta.id}/check_top.jpg?w=720", headers={"if-none-match": r.headers["etag"]}).status_code == 200
    assert client.get(f"/files/{meta.id}/nothing.jpg").status_code == 404
    assert "check_top.w720.jpg" not in client.get(f"/api/swings/{meta.id}").json().get("files", [])


def test_key_frame_addresses_change_with_each_analysis(client, runs):
    # Within one page a browser reuses a picture it already has at the same address, so
    # a re-analysis must give the key frames a new address (images_version).
    import os
    import time
    before = client.get("/api/swings/old_swing").json()["images_version"]
    later = time.time_ns() + 10**9
    os.utime(runs / "old_swing" / "analysis.json", ns=(later, later))
    assert client.get("/api/swings/old_swing").json()["images_version"] != before
    assert all("images_version" in s for s in client.get("/api/swings").json())


def test_first_save_of_marks_logs_how_long_marking_took(tmp_path):
    import json

    from swingcheck.app.store import Store
    from tests.helpers import make_info

    meta = Store(tmp_path).create("swing.mp4", "dtl")
    folder = tmp_path / meta.id
    make_info().save(folder / "video.json")
    client = TestClient(create_app(tmp_path))
    body = {"address_frame": 5, "points": {"ball": [1, 2], "clubhead": [3, 4], "grip": [5, 6]}, "checkpoints": {}}
    assert client.post(f"/api/swings/{meta.id}/marks", json=body).status_code == 200
    assert client.post(f"/api/swings/{meta.id}/marks", json=body).status_code == 200  # an edit: not counted
    logged = [json.loads(line) for line in (tmp_path / "admin-events.jsonl").read_text().splitlines()]
    marks = [e for e in logged if e["event"] == "marks"]
    assert len(marks) == 1 and marks[0]["mark_s"] >= 0 and set(marks[0]) == {"t", "event", "mark_s"}
