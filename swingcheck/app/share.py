"""Shared swing summaries: a link anyone can open, made only when the golfer asks.

Sharing saves a snapshot inside the swing's folder: the summary PDF, a preview picture
(the address, top, and impact frames), and the checkpoint counts for the preview card.
The link /s/<code> opens the PDF straight away (after a tiny page that only carries the
card for Messenger and others). The code is random and separate from the owner's key, so the link shows
this one summary and nothing else. Stop sharing deletes the snapshot; the swing's own
deletion (hosted: a few days after upload) takes it too.

The page never shows the video's file name, which can be a person's name.
"""

from __future__ import annotations

import html
import secrets
from pathlib import Path
from typing import Any

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


def page(share: dict[str, Any], base_url: str) -> str:
    """The shared link: straight to the PDF. Link previews (Messenger and others) read the
    card from this page's tags, which their crawlers fetch without running scripts; a
    browser goes on to the PDF at once (replace, so Back doesn't land here again)."""
    esc = html.escape
    code = share["code"]
    items = share.get("items", [])
    counts = {s: sum(i["status"] == s for i in items) for s in ("ok", "warn", "flag")}
    parts = [f"{counts['ok']} good", f"{counts['warn']} to watch", f"{counts['flag']} to fix"]
    description = f"{len(items)} checkpoints: {', '.join(parts[:-1])}, and {parts[-1]}."
    pdf = f"/s/{code}/summary.pdf"
    preview_url = f"{base_url}/s/{code}/preview.jpg"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex"><title>Swing check · SwingCheck</title><link rel="icon" href="/favicon.svg">
<meta property="og:type" content="website"><meta property="og:site_name" content="SwingCheck">
<meta property="og:title" content="A golf swing, checked"><meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{base_url}/s/{code}"><meta property="og:image" content="{preview_url}">
<meta name="twitter:card" content="summary_large_image"><meta name="twitter:image" content="{preview_url}">
<script>location.replace("{pdf}");</script>
<style>body {{ background: #101311; color: #e9ece6; font: 16px system-ui, sans-serif; margin: 24px; }} a {{ color: #7fd49a; }}</style>
</head><body><p>Opening the swing summary… <a href="{pdf}">Open the PDF</a></p></body></html>"""


def gone_page() -> str:
    """A shared link that was stopped, or whose swing was deleted: a plain page, not an error in JSON."""
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex"><title>Link not available · SwingCheck</title><link rel="icon" href="/favicon.svg">
<style>
body { margin: 0; min-height: 100vh; display: grid; place-items: center; padding: 24px 16px; box-sizing: border-box;
  background: #101311; color: #e9ece6; font: 16px/1.5 system-ui, sans-serif; text-align: center; }
main { width: 100%; max-width: 420px; }
.logo { width: 48px; height: 48px; }
h1 { margin: 16px 0 8px; font-size: 22px; }
p { margin: 0 0 24px; color: #a9b0a6; }
a.button { display: inline-block; padding: 12px 20px; border-radius: 999px; background: #2b7a47; color: #fff;
  font-weight: 600; text-decoration: none; }
a.button:hover { background: #338f54; }
</style></head><body><main>
<img class="logo" src="/favicon.svg" alt="">
<h1>This shared swing isn't available any more</h1>
<p>Its owner stopped sharing it, or the swing was deleted.</p>
<a class="button" href="/">Check your own swing</a>
</main></body></html>"""
