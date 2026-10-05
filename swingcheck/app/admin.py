"""The admin page (/admin): how the service is doing, in numbers only.

It never shows anyone's swings. Swings are deleted after a few days, so daily counts
come from a small event log next to them (admin-events.jsonl): what happened, when, and
how long it took. No videos, file names, IP addresses, or owner keys go in it, and
events older than KEEP_DAYS are dropped. To count unique uploaders per day, an upload
carries a code from the browser's key and a secret that changes every day and is never
saved (DailyCode): the same browser matches itself within a day, but days can't be linked.

Hosted, the page is behind Cloudflare Access (an email one-time code), and the app also
checks the address Access vouches for against SWINGCHECK_ADMIN_EMAIL; without that
setting the page doesn't exist. Run locally, it's open (it's your own computer).
"""

from __future__ import annotations

import hashlib
import hmac
import html
import json
import secrets
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


class DailyCode:
    """Codes for counting unique uploaders per day without following anyone across days:
    a keyed hash of the owner with a secret made fresh each (Philippine) day and kept only
    in memory. A restart mid-day starts a new secret, so a browser may count twice then."""

    def __init__(self) -> None:
        self._day = None
        self._secret = b""
        self._lock = threading.Lock()

    def code(self, owner: str, now: float | None = None) -> str:
        day = datetime.fromtimestamp(now or time.time(), LOCAL_TZ).date()
        with self._lock:
            if day != self._day:
                self._day, self._secret = day, secrets.token_bytes(32)
            return hmac.new(self._secret, owner.encode(), hashlib.sha256).hexdigest()[:16]


def summary(events: list[dict[str, Any]], live: dict[str, Any], now: float | None = None) -> dict[str, Any]:
    """Everything the page shows, as plain data (also handy for tests)."""
    now = now or time.time()
    today = datetime.fromtimestamp(now, LOCAL_TZ).date()
    days = [today - timedelta(days=i) for i in range(DAYS_SHOWN)]
    per_day = {d: Counter() for d in days}
    uploaders = {d: set() for d in days}
    for e in events:
        d = datetime.fromtimestamp(e["t"], LOCAL_TZ).date()
        if d in per_day:
            name = e["event"] if e["event"] == "upload" else f"{e['event']}_{'ok' if e.get('ok') else 'failed'}"
            per_day[d][name] += 1
            if e["event"] == "upload" and e.get("u"):
                uploaders[d].add(e["u"])

    week_ago = now - DAYS_SHOWN * 86400
    jobs = [e for e in events if e["event"] in ("convert", "analyze") and e["t"] >= week_ago]
    analyses = [e for e in jobs if e["event"] == "analyze" and e.get("ok")]
    waits = [e["wait_s"] for e in jobs if e.get("wait_s") is not None]
    month_ago = now - 30 * 86400
    camera = Counter(title for e in events if e["event"] == "convert" and e["t"] >= month_ago
                     for title in e.get("camera", []))
    # When people use it: uploads and finished analyses by hour of day (PHT), last 7 days.
    hours = {"upload": [0] * 24, "analyze": [0] * 24}
    for e in events:
        if e["t"] >= week_ago and (e["event"] == "upload" or (e["event"] == "analyze" and e.get("ok"))):
            hours[e["event"]][datetime.fromtimestamp(e["t"], LOCAL_TZ).hour] += 1
    return {
        "live": live,
        "days": [{"date": d.isoformat(), "uploaders": len(uploaders[d]), **{k: per_day[d][k] for k in (
            "upload", "convert_ok", "convert_failed", "analyze_ok", "analyze_failed")}} for d in days],
        "speed": {
            "median_wait_s": round(statistics.median(waits)) if waits else None,
            "longest_wait_s": round(max(waits)) if waits else None,
            "median_analysis_s": round(statistics.median(e["run_s"] for e in analyses)) if analyses else None,
        },
        "problems": [{"t": e["t"], "event": e["event"], "error": e.get("error", "")}
                     for e in sorted(events, key=lambda e: e["t"], reverse=True)
                     if e["event"] in ("convert", "analyze") and not e.get("ok")][:15],
        "camera": camera.most_common(5),
        "hours": hours,
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


def _day(iso: str) -> str:
    day = datetime.fromisoformat(iso)
    return f"{day:%a} {day.day}"  # "Mon 5": short enough for a phone


def _hour_chart(hours: dict[str, list[int]]) -> str:
    """A small line chart of activity by hour of day: uploads (bright green), analyses (orange)."""
    w, h, left, bottom, top = 640, 170, 28, 22, 10
    peak = max(1, *hours["upload"], *hours["analyze"])

    def x(i: int) -> float:
        return left + i * (w - left - 8) / 23

    def y(v: float) -> float:
        return top + (h - top - bottom) * (1 - v / peak)

    def line(values: list[int], color: str, dash: str = "") -> str:
        points = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(values))
        extra = f' stroke-dasharray="{dash}"' if dash else ""
        return (f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2.5" '
                f'stroke-linejoin="round" stroke-linecap="round"{extra}/>')

    grid = "".join(f'<line x1="{left}" x2="{w - 8}" y1="{y(v):.1f}" y2="{y(v):.1f}" class="grid"/>'
                   f'<text x="{left - 6}" y="{y(v) + 4:.1f}" text-anchor="end">{v}</text>'
                   for v in sorted({0, peak // 2, peak}))
    ticks = ((0, "12a"), (3, "3a"), (6, "6a"), (9, "9a"), (12, "12p"), (15, "3p"), (18, "6p"), (21, "9p"))
    labels = "".join(f'<text x="{x(i):.1f}" y="{h - 4}" text-anchor="middle">{t}</text>' for i, t in ticks)
    return (f'<svg class="chart" viewBox="0 0 {w} {h}" role="img" '
            f'aria-label="Uploads and analyses by hour of day, last {DAYS_SHOWN} days">{grid}{labels}'
            f'{line(hours["analyze"], "var(--plane)", "5 5")}{line(hours["upload"], "var(--bright)")}</svg>')


STYLE = """
  main { max-width: 920px; }
  .admin-bar .brand-sub { color: var(--on-deep-soft); font-size: 13px; font-weight: 500; }
  .tiles { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px; }
  .tile { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 12px 14px; }
  .tile .label, th { color: var(--muted); font-size: 12px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; }
  .tile .value { font-size: 26px; font-weight: 750; letter-spacing: -.02em; line-height: 1.2; margin-top: 4px; }
  .tile .sub { color: var(--muted); font-size: 13px; }
  h2 { display: flex; align-items: baseline; justify-content: space-between; flex-wrap: wrap; gap: 4px 8px; }
  h2 small { color: var(--muted); font-size: 13px; font-weight: 500; }
  table { width: 100%; border-collapse: collapse; font-variant-numeric: tabular-nums; }
  th, td { text-align: left; padding: 7px 8px; border-bottom: 1px solid var(--border); }
  .bad { color: var(--flag); } .muted { color: var(--muted); font-size: 13px; }
  ul { margin: 0; padding-left: 18px; } li { margin: 6px 0; overflow-wrap: anywhere; }
  .table-wrap { overflow-x: auto; }
  td, th { white-space: nowrap; }
  .chart { width: 100%; height: auto; display: block; }
  @media (max-width: 640px) {
    .admin-bar .brand-sub { display: none; }
    .tiles { grid-template-columns: 1fr 1fr; }
    .tile .value { font-size: 22px; }
    th, td { padding: 6px; }
    .chart text { font-size: 20px; }  /* the chart scales down to the phone: keep labels readable */
  }
  .chart text { fill: var(--muted); font-size: 11px; } .chart .grid { stroke: var(--border); stroke-width: 1; }
  .legend { display: flex; gap: 16px; font-size: 13px; color: var(--muted); margin-top: 6px; }
  .legend span::before { content: ""; display: inline-block; width: 16px; height: 3px; border-radius: 2px;
    margin-right: 6px; vertical-align: middle; background: var(--bright); }
  .legend .an::before { background: var(--plane); }
"""

LOGO = ('<svg class="brand-mark" viewBox="0 0 32 32" aria-hidden="true">'
        '<circle cx="16" cy="16" r="15" fill="#fff" fill-opacity="0.16"/><circle cx="16" cy="16" r="11" fill="#fff"/>'
        '<circle cx="13" cy="13.5" r="1.3" fill="#c9cec6"/><circle cx="18.5" cy="12.5" r="1.3" fill="#c9cec6"/>'
        '<circle cx="15.5" cy="18.5" r="1.3" fill="#c9cec6"/><circle cx="20" cy="17.5" r="1.3" fill="#c9cec6"/></svg>')

THEME = ('<script>try { if (localStorage.getItem("swingcheck.theme") === "light") '
         'document.documentElement.dataset.theme = "light"; } catch {}</script>')


def page(data: dict[str, Any]) -> str:
    """The admin page: the app's stylesheet and brand header, refreshing itself every 30 s."""
    esc = html.escape
    live = data["live"]
    doing = {"convert": "Converting", "analyze": "Analyzing"}
    running = ", ".join(f"{doing.get(r['kind'], r['kind'])} · {_duration(r['for_s'])}"
                        for r in live["running"]) or "Idle"

    def tile(label: str, value: Any, sub: str = "") -> str:
        return (f'<div class="tile"><div class="label">{label}</div><div class="value">{value}</div>'
                + (f'<div class="sub">{sub}</div>' if sub else "") + "</div>")

    tiles = "".join([
        tile("Processing now", esc(running)),
        tile("In line", live["queued"]),
        tile("Uploading", live["uploading"]),
        tile("Swings stored", live["swings_stored"]),
        tile("Disk used", f"{live['disk_used_pct']}%", f"{live['disk_free_gb']} GB free"),
        tile("Up for", _duration(live["up_s"]), esc(live["version"])),
    ])
    rows = "".join(
        f"<tr><td>{esc(_day(d['date']))}</td><td>{d['uploaders']}</td>"
        f"<td>{d['upload']}</td><td>{_count(d['convert_ok'], d['convert_failed'])}</td>"
        f"<td>{_count(d['analyze_ok'], d['analyze_failed'])}</td></tr>"
        for d in data["days"])
    problems = "".join(
        f"<li><span class=muted>{esc(datetime.fromtimestamp(p['t'], LOCAL_TZ).strftime('%b %d %H:%M'))} · "
        f"{esc(p['event'])}</span><br>{esc(p['error'][:300])}</li>" for p in data["problems"]) \
        or "<li class=muted>None in the last 90 days.</li>"
    camera = "".join(f"<li>{esc(title)} <span class=muted>× {n}</span></li>" for title, n in data["camera"]) \
        or "<li class=muted>None.</li>"
    speed = data["speed"]
    timing = (f"wait {_duration(speed['median_wait_s'])} typical, {_duration(speed['longest_wait_s'])} longest"
              f" · analysis {_duration(speed['median_analysis_s'])}")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="30"><meta name="robots" content="noindex"><meta name="theme-color" content="#123824">
<title>SwingCheck admin</title><link rel="icon" href="/favicon.svg"><link rel="stylesheet" href="/style.css">
{THEME}<style>{STYLE}</style></head><body>
<header class="topbar admin-bar"><span class="brand">{LOGO}<span class="brand-name">SwingCheck
  <span class="stage-badge">Admin</span></span></span>
  <span class="brand-sub">Numbers only · refreshes every 30 s</span></header>
<main class="stack">
<section class="tiles">{tiles}</section>
<section class="panel"><h2>Activity by hour <small>last {DAYS_SHOWN} days, PHT</small></h2>
{_hour_chart(data["hours"])}
<div class="legend"><span>Uploads</span><span class="an">Analyses</span></div></section>
<section class="panel"><h2>Last {DAYS_SHOWN} days <small>{timing}</small></h2>
<div class="table-wrap"><table><tr><th>Day</th><th>Uploaders</th><th>Uploads</th><th>Converted</th><th>Analyzed</th></tr>{rows}</table></div></section>
<section class="panel"><h2>Recent problems</h2><ul>{problems}</ul></section>
<section class="panel"><h2>Camera check problems <small>30 days</small></h2><ul>{camera}</ul></section>
</main></body></html>"""
