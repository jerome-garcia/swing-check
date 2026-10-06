"""Admin page: numbers only, open to the admin alone, and an event log with nothing personal."""

import json
import time

import pytest
from fastapi.testclient import TestClient

from swingcheck.app import admin
from swingcheck.app.server import create_app

ACCESS = {"cf-access-jwt-assertion": "jwt-from-cloudflare", "cf-access-authenticated-user-email": "Me@Example.com"}


def test_log_drops_old_events(tmp_path):
    log = admin.EventLog(tmp_path / "events.jsonl")
    log.add("upload", handedness="left")
    old = {"t": time.time() - (admin.KEEP_DAYS + 1) * 86400, "event": "upload"}
    with (tmp_path / "events.jsonl").open("a") as f:
        f.write(json.dumps(old) + "\nnot json\n")
    assert [e["handedness"] for e in log.read()] == ["left"]
    assert len((tmp_path / "events.jsonl").read_text().splitlines()) == 1  # the file was pruned too


def test_summary_counts_days_speed_and_problems():
    now = time.time()
    events = [
        {"t": now, "event": "upload", "handedness": "left", "u": "aaa"},
        {"t": now, "event": "upload", "handedness": "right", "u": "aaa"},  # same browser, same day
        {"t": now, "event": "upload", "handedness": "right", "u": "bbb", "upload_s": 12},
        {"t": now, "event": "upload", "handedness": "right", "u": "bbb", "upload_s": 30},
        {"t": now, "event": "convert", "ok": True, "wait_s": 2, "run_s": 10, "camera": ["You're small in the frame"]},
        {"t": now, "event": "analyze", "ok": True, "wait_s": 60, "run_s": 80},
        {"t": now, "event": "analyze", "ok": False, "wait_s": 4, "run_s": 5, "error": "Boom"},
        {"t": now, "event": "marks", "mark_s": 70},
        {"t": now, "event": "marks", "mark_s": 110},
        {"t": now, "event": "marks", "mark_s": 3600},  # left open: the median isn't thrown by it
    ]
    live = {"version": "v1", "up_s": 5, "running": [], "queued": 0, "uploading": 0, "swings_stored": 2,
            "disk_free_gb": 30.0, "disk_used_pct": 18, "swings_bytes": 412_000_000}
    s = admin.summary(events, live, now)
    assert s["days"][0] == {"date": s["days"][0]["date"], "uploaders": 2, "upload": 4, "convert_ok": 1,
                            "convert_failed": 0, "analyze_ok": 1, "analyze_failed": 1}
    assert s["speed"] == {"median_wait_s": 4, "longest_wait_s": 60, "median_analysis_s": 80,
                          "average_wait_s": 22, "average_upload_s": 21, "median_marking_s": 110}
    assert s["problems"][0]["error"] == "Boom"
    assert s["camera"] == [("You're small in the frame", 1)]
    page = admin.page(s)
    assert "SwingCheck admin" in page and "+1 failed" in page and "Boom" in page
    assert "Active browsers" not in page and "Uploaders" in page and "Idle" in page and "In line" in page
    assert "avg wait 22 s" in page and "avg upload 21 s" in page and "412 MB" in page
    assert "analysis 1 min typical · marking 2 min typical" in page
    assert "one at a time" not in page and "since the last restart" not in page  # descriptions removed
    live["running"] = [{"kind": "analyze", "for_s": 45}]
    assert '<div class="value">Analyzing</div><div class="sub">45 s</div>' in admin.page(admin.summary(events, live, now))
    hour = admin.datetime.fromtimestamp(now, admin.LOCAL_TZ).hour
    assert s["hours"]["upload"][hour] == 4 and s["hours"]["analyze"][hour] == 1 and sum(s["hours"]["analyze"]) == 1
    assert page.count("<polyline") == 2  # the hour chart: uploads and analyses


def test_admin_is_open_on_your_own_computer(tmp_path):
    assert TestClient(create_app(tmp_path)).get("/admin").status_code == 200


@pytest.mark.parametrize("env, headers, status", [
    (None, ACCESS, 404),                                       # no admin set on the server: no page
    ("me@example.com", {}, 404),                               # not through Cloudflare Access
    ("me@example.com", {**ACCESS, "cf-access-authenticated-user-email": "someone@else.com"}, 404),
    ("me@example.com", {"cf-access-authenticated-user-email": "me@example.com"}, 404),  # no Access token
    ("me@example.com", ACCESS, 200),
])
def test_admin_hosted_only_for_the_admin(tmp_path, monkeypatch, env, headers, status):
    if env:
        monkeypatch.setenv("SWINGCHECK_ADMIN_EMAIL", env)
    else:
        monkeypatch.delenv("SWINGCHECK_ADMIN_EMAIL", raising=False)
    client = TestClient(create_app(tmp_path, hosted=True))
    assert client.get("/admin", headers=headers).status_code == status


def test_uploads_and_jobs_are_logged_without_anything_personal(tmp_path):
    client = TestClient(create_app(tmp_path, hosted=True))
    r = client.post("/api/swings", files={"file": ("Juan dela Cruz swing.mov", b"not really a video")},
                    data={"view": "dtl", "handedness": "left", "agreed_terms": "2026-10-05"})
    client.app.state.jobs.wait(r.json()["job"]["id"], timeout=60)
    log = (tmp_path / admin.EVENTS_FILE).read_text()
    events = [json.loads(line) for line in log.splitlines()]
    assert [e["event"] for e in events] == ["upload", "convert"]
    assert events[0]["handedness"] == "left" and events[1]["ok"] is False and events[1]["error"]
    assert events[0]["upload_s"] >= 0  # how long sending the video took
    assert len(events[0]["u"]) == 16  # today's code for this browser, not its key or owner hash
    swing_id = r.json()["id"]
    from swingcheck.app.hosted import owner_of
    key = client.cookies.get("swingcheck_owner")
    for secret in ("Juan", swing_id, "testclient", key, owner_of(key)):
        assert secret not in log


def test_daily_codes_match_within_a_day_only():
    codes = admin.DailyCode()
    noon = 1791172800  # a midday in the Philippines
    a = codes.code("owner-1", noon)
    assert a == codes.code("owner-1", noon + 3600) != codes.code("owner-2", noon)
    assert codes.code("owner-1", noon + 86400) != a  # the next day: a new secret, so no link

