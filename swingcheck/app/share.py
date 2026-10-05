"""Shared swing summaries: a link anyone can open, made only when the golfer asks.

Sharing saves a snapshot inside the swing's folder: the summary PDF, a preview picture
(the address, top, and impact frames), and the checkpoint list. A page at /s/<code>
shows the picture and the list, links to the PDF, and gives Messenger and others a
preview card. The code is random and separate from the owner's key, so the link shows
this one summary and nothing else. Stop sharing deletes the snapshot; the swing's own
deletion (hosted: a few days after upload) takes it too.

The page never shows the video's file name, which can be a person's name.
"""

from __future__ import annotations

import html
import secrets
from datetime import datetime
from pathlib import Path
from typing import Any

from swingcheck.app.admin import LOGO
from swingcheck.checkpoints import DTL_CHECKPOINTS

PDF_FILE = "shared-summary.pdf"
PREVIEW_FILE = "shared-preview.jpg"
STATUS_WORD = {"ok": "Good", "warn": "Watch", "flag": "Fix", "error": "Not marked"}


def new_code() -> str:
    return secrets.token_urlsafe(16)


def snapshot_items(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    """The checkpoint list as it stands now: number, title, status, and the short result."""
    by_name = {v.get("name"): v for v in analysis.get("verdicts", [])}
    items = []
    for cp in DTL_CHECKPOINTS:
        v = by_name.get(cp.analyzer)
        if v is not None:
            items.append({"number": cp.number, "title": cp.title, "status": v.get("status", "error"),
                          "label": v.get("label", "")})
    return items


def write_preview(summary_png: Path, out: Path) -> bool:
    """The link-preview picture: the key-frame sheet as a JPEG at most 1200 px wide."""
    import cv2

    img = cv2.imread(str(summary_png)) if summary_png.exists() else None
    if img is None:
        return False
    if img.shape[1] > 1200:
        img = cv2.resize(img, (1200, round(img.shape[0] * 1200 / img.shape[1])), interpolation=cv2.INTER_AREA)
    ok, data = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 82])
    if ok:
        out.write_bytes(data.tobytes())
    return bool(ok)


def page(share: dict[str, Any], base_url: str, details: str, until: datetime | None, has_preview: bool) -> str:
    """The shared page: brand bar, preview picture, checkpoint list, PDF button, and an
    invitation to check your own swing. `details` is e.g. "Down-the-line · Right-handed"."""
    esc = html.escape
    code = share["code"]
    items = share.get("items", [])
    counts = {s: sum(i["status"] == s for i in items) for s in ("ok", "warn", "flag")}
    parts = [f"{counts['ok']} good", f"{counts['warn']} to watch", f"{counts['flag']} to fix"]
    description = f"{len(items)} checkpoints: {', '.join(parts[:-1])}, and {parts[-1]}."
    preview_url = f"{base_url}/s/{code}/preview.jpg"
    rows = "".join(
        f'<li><span class="score-dot {esc(i["status"])}">{i["number"]}</span>'
        f'<span><strong>{esc(i["title"])}</strong> <span class="word {esc(i["status"])}">'
        f'{STATUS_WORD.get(i["status"], "")}</span><br><span class="subtle">{esc(i["label"])}</span></span></li>'
        for i in items)
    until_text = f" · Link works until {until:%b} {until.day}" if until else ""
    og_image = (f'<meta property="og:image" content="{preview_url}"><meta name="twitter:image" content="{preview_url}">'
                if has_preview else "")
    picture = (f'<a href="/s/{code}/summary.pdf"><img class="share-img" src="/s/{code}/preview.jpg" '
               'alt="Address, top, and impact frames"></a>' if has_preview else "")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex"><meta name="theme-color" content="#123824">
<title>Swing check · SwingCheck</title><link rel="icon" href="/favicon.svg"><link rel="stylesheet" href="/style.css">
<meta property="og:type" content="website"><meta property="og:site_name" content="SwingCheck">
<meta property="og:title" content="A golf swing, checked"><meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{base_url}/s/{code}"><meta name="twitter:card" content="summary_large_image">{og_image}
<script>try {{ if (localStorage.getItem("swingcheck.theme") === "light") document.documentElement.dataset.theme = "light"; }} catch {{}}</script>
<style>
  main {{ max-width: 760px; }}
  .share-img {{ width: 100%; height: auto; display: block; border-radius: var(--radius); }}
  .share-list {{ list-style: none; margin: 0; padding: 0; display: grid; gap: 12px; }}
  .share-list li {{ display: flex; gap: 12px; align-items: flex-start; }}
  .share-list .score-dot {{ flex: none; }}
  .word {{ font-size: 13px; font-weight: 700; }} .word.ok {{ color: var(--ok); }}
  .word.warn {{ color: var(--warn); }} .word.flag {{ color: var(--flag); }}
</style></head><body>
<header class="topbar"><a class="brand" href="/" aria-label="SwingCheck">{LOGO}<span class="brand-text">
  <span class="brand-name">SwingCheck</span></span></a>
  <a class="btn primary" href="/new">Check your swing</a></header>
<main class="stack">
<section><h1>Swing check</h1><div class="subtle small">{esc(details)}{esc(until_text)}</div></section>
{picture}
<section class="panel"><h2>Checkpoints</h2><p class="subtle">{esc(description)}</p><ul class="share-list">{rows}</ul></section>
<div class="actions"><a class="btn primary" href="/s/{code}/summary.pdf">View the PDF</a>
  <a class="btn" href="/new">Check your own swing →</a></div>
<p class="subtle small">Checked with SwingCheck from a phone video: estimates for practice, not professional coaching.</p>
</main></body></html>"""
