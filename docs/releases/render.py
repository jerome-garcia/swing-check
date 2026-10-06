"""Release notes as PDFs: one A4 page per minor release, from the Markdown beside this file.

    python docs/releases/render.py            # every vX.Y.md -> swingcheck-X.Y-release-notes.pdf
    python docs/releases/render.py v0.6.md    # just that one

Each vX.Y.md: "# Title", a "Released ..." line, an intro paragraph, then "## " sections of
"- " bullets (**bold** allowed). The page uses the brand's colors and logo (branding/) and is
printed with headless Edge, like branding/render.sh (Windows).
"""

from __future__ import annotations

import html
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOGO = (HERE.parent.parent / "branding" / "logo-on-dark.svg").as_uri()
EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")

STYLE = """
@page { size: A4; margin: 0; }
:root { --fairway: #2b7a47; --deep: #123824; --deeper: #0d2a1b; --bright: #4fb06d;
  --paper: #f4f5f2; --ink: #1a1d19; --muted: #5f665d; --rule: #dfe2db; }
* { box-sizing: border-box; }
html, body { margin: 0; }
body { width: 794px; height: 1123px; display: flex; flex-direction: column; overflow: hidden; background: var(--paper); color: var(--ink);
  font: 13px/1.55 "Segoe UI", system-ui, sans-serif; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
header { background: var(--deep); color: #fff; padding: 34px 48px 30px; }
.lockup { display: flex; align-items: center; gap: 9px; font-size: 18px; font-weight: 750; letter-spacing: -0.035em; }
.lockup img { width: 28px; height: 28px; }
.lockup .tag { margin-left: 6px; padding: 1px 8px; border: 1px solid var(--bright); border-radius: 999px; color: var(--bright);
  font-size: 10px; font-weight: 700; letter-spacing: 0.12em; }
h1 { margin: 26px 0 4px; font-size: 40px; font-weight: 750; line-height: 1.05; letter-spacing: -0.035em; }
.meta { color: rgba(255, 255, 255, 0.7); font-size: 13px; }
main { flex: 1; padding: 28px 48px 40px; }
.intro { margin: 0 0 22px; font-size: 16px; line-height: 1.45; }
h2 { display: flex; align-items: center; gap: 8px; margin: 22px 0 10px; padding-top: 18px; border-top: 1px solid var(--rule);
  font-size: 17px; font-weight: 700; letter-spacing: -0.01em; color: var(--deep); }
h2::before { content: ""; width: 8px; height: 8px; border-radius: 50%; background: var(--bright); }
ul { margin: 0; padding: 0; list-style: none; }
li { position: relative; margin: 0 0 9px; padding-left: 18px; }
li::before { content: ""; position: absolute; left: 2px; top: 8px; width: 6px; height: 6px; border-radius: 50%; background: var(--fairway); }
b { color: var(--deep); }
footer { padding: 0 48px 30px; color: var(--muted); font-size: 11px; }
"""


def inline(text: str) -> str:
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", html.escape(text))


def to_html(md: str) -> str:
    lines = [line.rstrip() for line in md.splitlines()]
    title = lines[0].removeprefix("# ").strip()
    meta = lines[1].strip()
    body, bullets = [], []

    def flush() -> None:
        if bullets:
            body.append("<ul>" + "".join(f"<li>{inline(b)}</li>" for b in bullets) + "</ul>")
            bullets.clear()

    for line in lines[2:]:
        if line.startswith("## "):
            flush()
            body.append(f"<h2>{inline(line[3:])}</h2>")
        elif line.startswith("- "):
            bullets.append(line[2:])
        elif line.strip():
            flush()
            body.append(f'<p class="intro">{inline(line)}</p>')
    flush()
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{html.escape(title)} release notes</title>
<style>{STYLE}</style></head><body>
<header><div class="lockup"><img src="{LOGO}" alt="">SwingCheck<span class="tag">ALPHA</span></div>
<h1>{html.escape(title)}</h1><div class="meta">{html.escape(meta)}</div></header>
<main>{''.join(body)}</main>
<footer>swingcheck.org · Results are estimates from video, for practice only.</footer>
</body></html>"""


def render(md_path: Path) -> Path:
    version = md_path.stem.removeprefix("v")
    out = HERE / f"swingcheck-{version}-release-notes.pdf"
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / "notes.html"
        page.write_text(to_html(md_path.read_text(encoding="utf-8")), encoding="utf-8")
        subprocess.run([str(EDGE), "--headless", "--disable-gpu", "--no-pdf-header-footer",
                        f"--print-to-pdf={out}", page.as_uri()], check=True, capture_output=True)
    return out


if __name__ == "__main__":
    names = sys.argv[1:] or sorted(p.name for p in HERE.glob("v*.md"))
    for name in names:
        print(render(HERE / name).name)
