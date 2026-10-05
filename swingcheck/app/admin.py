"""The admin page (/admin): how the service is doing, in numbers only.

It never shows anyone's swings. Swings are deleted after a few days, so daily counts
come from a small event log next to them (admin-events.jsonl): what happened, when, and
how long it took. No videos, file names, IP addresses, or owner keys go in it, and
events older than KEEP_DAYS are dropped.

Hosted, the page is behind Cloudflare Access (an email one-time code), and the app also
checks the address Access vouches for against SWINGCHECK_ADMIN_EMAIL; without that
setting the page doesn't exist. Run locally, it's open (it's your own computer).
"""

from __future__ import annotations

import html
import json
import shutil
import statistics
import threading
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

EVENTS_FILE = "admin-events.jsonl"
KEEP_DAYS = 90
LOCAL_TZ = timezone(timedelta(hours=8), "PHT")  # dates on the page: Philippine time
DAYS_SHOWN = 7


class EventLog:
    """Append-only JSON lines; old events are dropped when the log is read."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()

    def add(self, event: str, **fields: Any) -> None:
        line = json.dumps({"t": round(time.time(), 1), "event": event, **fields})
        with self._lock, self.path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    def read(self, now: float | None = None) -> list[dict[str, Any]]:
        cutoff = (now or time.time()) - KEEP_DAYS * 86400
        with self._lock:
            if not self.path.exists():
                return []
            lines = self.path.read_text(encoding="utf-8").splitlines()
            events = []
            for line in lines:
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                if e.get("t", 0) >= cutoff:
                    events.append(e)
            if len(events) < len(lines):  # drop the old (and any broken) lines
                self.path.write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
        return events


def summary(events: list[dict[str, Any]], live: dict[str, Any], now: float | None = None) -> dict[str, Any]:
    """Everything the page shows, as plain data (also handy for tests)."""
    now = now or time.time()
    today = datetime.fromtimestamp(now, LOCAL_TZ).date()
    days = [today - timedelta(days=i) for i in range(DAYS_SHOWN)]
    per_day = {d: Counter() for d in days}
    for e in events:
        d = datetime.fromtimestamp(e["t"], LOCAL_TZ).date()
        if d in per_day:
            name = e["event"] if e["event"] == "upload" else f"{e['event']}_{'ok' if e.get('ok') else 'failed'}"
            per_day[d][name] += 1

    week_ago = now - DAYS_SHOWN * 86400
    jobs = [e for e in events if e["event"] in ("convert", "analyze") and e["t"] >= week_ago]
    analyses = [e for e in jobs if e["event"] == "analyze" and e.get("ok")]
    waits = [e["wait_s"] for e in jobs if e.get("wait_s") is not None]
    month_ago = now - 30 * 86400
    uploads = [e for e in events if e["event"] == "upload" and e["t"] >= month_ago]
    camera = Counter(title for e in events if e["event"] == "convert" and e["t"] >= month_ago
                     for title in e.get("camera", []))
    return {
        "live": live,
        "days": [{"date": d.isoformat(), **{k: per_day[d][k] for k in (
            "upload", "convert_ok", "convert_failed", "analyze_ok", "analyze_failed")}} for d in days],
        "speed": {
            "median_wait_s": round(statistics.median(waits)) if waits else None,
            "longest_wait_s": round(max(waits)) if waits else None,
            "median_analysis_s": round(statistics.median(e["run_s"] for e in analyses)) if analyses else None,
        },
        "problems": [{"t": e["t"], "event": e["event"], "error": e.get("error", "")}
                     for e in sorted(events, key=lambda e: e["t"], reverse=True)
                     if e["event"] in ("convert", "analyze") and not e.get("ok")][:15],
        "handedness": dict(Counter(e.get("handedness", "right") for e in uploads)),
        "camera": camera.most_common(5),
    }


def live_status(jobs, uploading: int, runs_dir: Path, version: str, started: float) -> dict[str, Any]:
    now = time.time()
    running = [j for j in jobs if j.state == "running"]
    disk = shutil.disk_usage(runs_dir)
    return {
        "version": version,
        "up_s": now - started,
        "running": [{"kind": j.kind, "for_s": now - (j.started or now)} for j in running],
        "queued": sum(j.state == "queued" for j in jobs),
        "uploading": uploading,
        "swings_stored": sum(1 for p in runs_dir.iterdir() if p.is_dir()),
        "disk_free_gb": round(disk.free / 1e9, 1),
        "disk_used_pct": round(100 * (disk.total - disk.free) / disk.total),
    }


def _duration(seconds: float | None) -> str:
    if seconds is None:
        return "–"
    seconds = round(seconds)
    if seconds < 90:
        return f"{seconds} s"
    if seconds < 90 * 60:
        return f"{round(seconds / 60)} min"
    if seconds < 48 * 3600:
        return f"{round(seconds / 3600)} h"
    return f"{round(seconds / 86400)} days"


def _count(ok: int, failed: int) -> str:
    return f"{ok}" + (f' <span class="bad">+{failed} failed</span>' if failed else "")


def page(data: dict[str, Any]) -> str:
    """The admin page: plain HTML on the app's stylesheet, refreshing itself every 30 s."""
    esc = html.escape
    live = data["live"]
    running = ", ".join(f"{r['kind']} ({_duration(r['for_s'])})" for r in live["running"]) or "nothing"
    rows = "".join(
        f"<tr><td>{esc(datetime.fromisoformat(d['date']).strftime('%a %b %d'))}</td><td>{d['upload']}</td>"
        f"<td>{_count(d['convert_ok'], d['convert_failed'])}</td><td>{_count(d['analyze_ok'], d['analyze_failed'])}</td></tr>"
        for d in data["days"])
    problems = "".join(
        f"<li><span class=muted>{esc(datetime.fromtimestamp(p['t'], LOCAL_TZ).strftime('%b %d %H:%M'))} · "
        f"{esc(p['event'])}</span><br>{esc(p['error'][:300])}</li>" for p in data["problems"]) \
        or "<li class=muted>None in the last 90 days.</li>"
    hands = data["handedness"]
    camera = "".join(f"<li>{esc(title)} <span class=muted>× {n}</span></li>" for title, n in data["camera"]) \
        or "<li class=muted>None.</li>"
    speed = data["speed"]
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="30"><meta name="robots" content="noindex">
<title>SwingCheck admin</title><link rel="icon" href="/favicon.svg"><link rel="stylesheet" href="/style.css">
<style>
  main {{ max-width: 860px; }}
  .grid2 {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 12px; }}
  .stat {{ font-size: 22px; font-weight: 700; }}
  table {{ width: 100%; border-collapse: collapse; font-variant-numeric: tabular-nums; }}
  th, td {{ text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--border); }}
  .bad {{ color: var(--flag); }} .muted {{ color: var(--muted); font-size: 13px; }}
  ul {{ margin: 0; padding-left: 18px; }} li {{ margin: 4px 0; overflow-wrap: anywhere; }}
</style></head><body><main class="stack">
<h1>SwingCheck admin</h1>
<p class="muted">Numbers only: no swings, names, IP addresses, or keys. Refreshes every 30 s.</p>
<section class="panel"><h2>Now</h2><div class="grid2">
  <div><div class="muted">Running</div><div class="stat">{esc(running)}</div></div>
  <div><div class="muted">Queued · uploading</div><div class="stat">{live['queued']} · {live['uploading']}</div></div>
  <div><div class="muted">Swings stored</div><div class="stat">{live['swings_stored']}</div></div>
  <div><div class="muted">Disk</div><div class="stat">{live['disk_used_pct']}% used</div><div class="muted">{live['disk_free_gb']} GB free</div></div>
  <div><div class="muted">Version · up for</div><div class="stat">{esc(live['version'])}</div><div class="muted">{_duration(live['up_s'])}</div></div>
</div></section>
<section class="panel"><h2>Last {DAYS_SHOWN} days</h2>
<table><tr><th>Day (PHT)</th><th>Uploads</th><th>Converted</th><th>Analyzed</th></tr>{rows}</table>
<p class="muted">Typical wait in line {_duration(speed['median_wait_s'])} (longest {_duration(speed['longest_wait_s'])}) ·
typical analysis {_duration(speed['median_analysis_s'])}</p></section>
<section class="panel"><h2>Recent problems</h2><ul>{problems}</ul></section>
<div class="grid2">
<section class="panel"><h2>Golfers (30 days)</h2><p>Right-handed {hands.get('right', 0)} · left-handed {hands.get('left', 0)}</p></section>
<section class="panel"><h2>Camera check (30 days)</h2><ul>{camera}</ul></section>
</div>
</main></body></html>"""
