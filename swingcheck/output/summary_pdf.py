"""A shareable one-file summary of an analyzed swing, as a PDF.

Built from what a run folder already holds (analysis.json and the check_<name>.png
key frames), so it needs no re-analysis. Layout: title, an 8-checkpoint scorecard,
the one thing to work on first, then one block per checkpoint (key frame beside its
result, readings with their green/red limits, and how to fix), and short notes on
how to read it.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import cv2
from fpdf import FPDF

from swingcheck.checkpoints import DTL_CHECKPOINTS

STATUS_WORD = {"ok": "Good", "warn": "Watch", "flag": "Fix", "error": "Not marked", "missing": "Not run"}
STATUS_RGB = {"ok": (35, 130, 79), "warn": (183, 121, 31), "flag": (194, 65, 45),
              "error": (120, 128, 124), "missing": (120, 128, 124)}
TINT_RGB = {"ok": (227, 242, 233), "warn": (251, 240, 220), "flag": (251, 228, 223),
            "error": (238, 240, 238), "missing": (238, 240, 238)}
INK, MUTED, LINE, TURF = (24, 34, 28), (91, 106, 96), (217, 224, 218), (31, 107, 69)

# A Unicode font so ≈, °, ±, – print as themselves; the first found wins.
FONT_CANDIDATES = [
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    ("C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/segoeuib.ttf"),
    ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
    ("/Library/Fonts/Arial.ttf", "/Library/Fonts/Arial Bold.ttf"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/usr/share/fonts/TTF/DejaVuSans.ttf", "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"),
]
# Without one, fall back to the built-in Helvetica, which only covers Latin-1.
LATIN1_SWAPS = {"≈": "~", "–": "-", "—": "-", "−": "-", "·": "|", "’": "'", "“": '"', "”": '"', "→": "->"}

PAGE_W, MARGIN = 210, 14
CONTENT_W = PAGE_W - 2 * MARGIN
IMG_W = 44  # key frame width in mm; height follows the frame's aspect


def _cap(s: str) -> str:
    return s[:1].upper() + s[1:]


class _Doc(FPDF):
    def __init__(self, footer_text: str):
        super().__init__(format="A4", unit="mm")
        self.footer_text = footer_text
        self.set_margins(MARGIN, MARGIN, MARGIN)
        self.set_auto_page_break(True, margin=16)
        self.unicode = False
        for regular, bold in FONT_CANDIDATES:
            if Path(regular).exists() and Path(bold).exists():
                self.add_font("body", "", regular)
                self.add_font("body", "B", bold)
                self.unicode = True
                break

    def font(self, size: float, bold: bool = False, color=INK) -> None:
        self.set_font("body" if self.unicode else "helvetica", "B" if bold else "", size)
        self.set_text_color(*color)

    def text_ok(self, s: str) -> str:
        if self.unicode:
            return s
        for a, b in LATIN1_SWAPS.items():
            s = s.replace(a, b)
        return s.encode("latin-1", "replace").decode("latin-1")

    def footer(self) -> None:
        self.set_y(-11)
        self.font(7.5, color=MUTED)
        self.cell(0, 4, self.text_ok(self.footer_text), align="L")
        self.cell(0, 4, f"Page {self.page_no()}/{{nb}}", align="R")

    def para(self, w: float, h: float, s: str, dry: bool = False, **kw) -> float:
        """multi_cell that returns its height; dry=True only measures."""
        kw.setdefault("align", "L")
        if dry:
            return self.multi_cell(w, h, self.text_ok(s), dry_run=True, output="HEIGHT", **kw)
        y = self.get_y()
        self.multi_cell(w, h, self.text_ok(s), new_x="LEFT", new_y="NEXT", **kw)
        return self.get_y() - y


def _key_frame(folder: Path, name: str) -> tuple[io.BytesIO, float] | None:
    """The checkpoint's key frame as a small JPEG, and its height/width ratio."""
    path = folder / f"check_{name}.png"
    img = cv2.imread(str(path)) if path.exists() else None
    if img is None:
        return None
    h, w = img.shape[:2]
    small = cv2.resize(img, (540, int(round(h * 540 / w))), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return (io.BytesIO(buf.tobytes()), h / w) if ok else None


def _note_text(r: dict[str, Any]) -> str:
    """The row's verdict, then its Good / Fix ranges on the next line."""
    ranges = " · ".join(t for t in (f"Good {r['good']}" if r.get("good") else "",
                                    f"Fix {r['fix']}" if r.get("fix") else "") if t)
    return "\n".join(t for t in (r.get("note", ""), ranges) if t)


def _row_height(doc: _Doc, r: dict[str, Any], text_w: float, lab_w: float, val_w: float) -> float:
    doc.font(8.5, True)
    h = max(doc.para(lab_w - 6, 4, r.get("label", ""), dry=True), doc.para(val_w - 2, 4, r.get("value", ""), dry=True))
    doc.font(8.5)
    return max(4.4, h, doc.para(text_w - lab_w - val_w, 4, _note_text(r), dry=True))


def _items(view: str, verdicts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Checkpoints in swing order with their verdicts (DTL), else the verdicts as listed."""
    by_name = {v.get("name"): v for v in verdicts}
    if view == "dtl":
        out = []
        for cp in DTL_CHECKPOINTS:
            v = by_name.get(cp.analyzer)
            out.append({"number": cp.number, "title": cp.title, "name": cp.analyzer,
                        "status": v["status"] if v else "missing", "verdict": v})
        return out
    return [{"number": i, "title": v.get("title", ""), "name": v.get("name"), "status": v.get("status", "missing"),
             "verdict": v} for i, v in enumerate(verdicts, 1)]


def summary_pdf(folder: Path, swing_name: str, created: str, analysis: dict[str, Any], torso_cm: float = 50) -> bytes:
    """Render the summary PDF for an analyzed run folder."""
    view = analysis.get("view", "dtl")
    items = _items(view, analysis.get("verdicts", []))
    date = created[:10] if created else ""
    doc = _Doc(f"SwingCheck · {swing_name} · {date}")
    doc.alias_nb_pages()
    doc.add_page()

    # Title.
    doc.font(8.5, True, TURF)
    doc.cell(0, 5, doc.text_ok("SWINGCHECK · " + ("DOWN THE LINE" if view == "dtl" else "FACE ON")),
             new_x="LMARGIN", new_y="NEXT")
    doc.font(22, True)
    doc.cell(0, 11, doc.text_ok(f"Swing summary: {swing_name}"), new_x="LMARGIN", new_y="NEXT")
    doc.font(10, color=MUTED)
    doc.cell(0, 6, doc.text_ok(f"Filmed {date} · {len(items)} checkpoints from address to follow-through"
                               if view == "dtl" else f"Filmed {date}"), new_x="LMARGIN", new_y="NEXT")
    doc.ln(4)

    # Scorecard: one box per checkpoint, colored bar on top.
    cols = min(8, max(1, len(items)))
    box_w, box_h = CONTENT_W / cols, 22
    y0 = doc.get_y()
    for i, it in enumerate(items[:cols]):
        x = MARGIN + i * box_w
        doc.set_draw_color(*LINE)
        doc.set_fill_color(255, 255, 255)
        doc.rect(x, y0, box_w, box_h, style="DF")
        doc.set_fill_color(*STATUS_RGB[it["status"]])
        doc.rect(x, y0, box_w, 1.6, style="F")
        doc.set_xy(x + 2, y0 + 3)
        doc.font(13, True)
        doc.cell(box_w - 4, 6, str(it["number"]))
        doc.set_xy(x + 1.5, y0 + 9)
        doc.font(7)
        doc.multi_cell(box_w - 2.5, 3.2, doc.text_ok(it["title"]), align="L")
        doc.set_xy(x + 2, y0 + box_h - 5)
        doc.font(7, True, STATUS_RGB[it["status"]])
        doc.cell(box_w - 4, 3.5, STATUS_WORD[it["status"]].upper())
    doc.set_xy(MARGIN, y0 + box_h + 3)
    counts = {k: sum(it["status"] == k for it in items) for k in ("ok", "warn", "flag")}
    doc.font(9.5, color=MUTED)
    doc.cell(0, 5, f"{counts['ok']} good   ·   {counts['warn']} to watch   ·   {counts['flag']} to fix"
             if doc.unicode else f"{counts['ok']} good  |  {counts['warn']} to watch  |  {counts['flag']} to fix",
             new_x="LMARGIN", new_y="NEXT")
    doc.ln(4)

    # The one thing to work on: the first red checkpoint in swing order, else the first yellow.
    # The saved pick (importance tiers + how far into red, swingcheck/priority.py); older
    # analyses: the first red checkpoint in swing order, else the first yellow.
    picked = analysis.get("focus")
    focus = next((it for it in items if picked and it["name"] == picked.get("checkpoint") and it["verdict"]), None) \
        or next((it for st in ("flag", "warn") for it in items if it["status"] == st and it["verdict"]), None)
    if focus:
        v, st = focus["verdict"], focus["status"]
        kicker = ("WORK ON FIRST" if st == "flag" else "WORTH A LOOK") + f" · {focus['number']}. {focus['title'].upper()}"
        doc.font(13, True)
        h_label = doc.para(CONTENT_W - 10, 6, _cap(v.get("label", "")), dry=True)
        doc.font(10)
        h_tip = doc.para(CONTENT_W - 10, 5, v.get("tip", ""), dry=True) if v.get("tip") else 0
        h = 6 + 5 + h_label + h_tip + 5
        y = doc.get_y()
        doc.set_fill_color(*TINT_RGB[st])
        doc.rect(MARGIN, y, CONTENT_W, h, style="F")
        doc.set_xy(MARGIN + 5, y + 4)
        doc.font(8, True, STATUS_RGB[st])
        doc.cell(0, 4, doc.text_ok(kicker), new_x="LEFT", new_y="NEXT")
        doc.set_x(MARGIN + 5)
        doc.ln(1)
        doc.set_x(MARGIN + 5)
        doc.font(13, True)
        doc.para(CONTENT_W - 10, 6, _cap(v.get("label", "")))
        if v.get("tip"):
            doc.set_x(MARGIN + 5)
            doc.font(10)
            doc.para(CONTENT_W - 10, 5, v["tip"])
        doc.set_xy(MARGIN, y + h + 6)

    # One block per checkpoint.
    text_x = MARGIN + IMG_W + 6
    text_w = PAGE_W - MARGIN - text_x
    val_w, lab_w = 34, 36
    for it in items:
        v, st = it["verdict"], it["status"]
        frame = _key_frame(folder, it["name"]) if v and it["name"] else None
        img_h = IMG_W * frame[1] if frame else 0
        rows = [r for r in (v or {}).get("rows", []) if not str(r.get("label", "")).endswith(" frame")]
        tip = v.get("tip", "") if v and st not in ("ok",) else ""

        # Measure the text column so a block never splits across pages.
        doc.font(11, True)
        h_text = 8 + (doc.para(text_w, 5.5, _cap(v.get("label", "")), dry=True) if v else 5)
        doc.font(9.5)
        h_text += doc.para(text_w, 4.6, v.get("summary", "") if v else "Not analyzed yet.", dry=True) + 3
        doc.font(8.5)
        for r in rows:
            h_text += _row_height(doc, r, text_w, lab_w, val_w) + 2.2
        if tip:
            doc.font(9.5)
            h_text += 6 + doc.para(text_w - 4, 4.6, tip, dry=True) + 2
        block_h = max(img_h, h_text) + 8
        if doc.get_y() + block_h > doc.h - 18:
            doc.add_page()

        y = doc.get_y()
        doc.set_draw_color(*LINE)
        doc.line(MARGIN, y, PAGE_W - MARGIN, y)
        y += 4
        if frame:
            doc.image(frame[0], x=MARGIN, y=y, w=IMG_W, h=img_h)

        # Header: number, title, status word.
        doc.set_xy(text_x, y)
        doc.font(15, True, MUTED)
        doc.cell(7, 7, str(it["number"]))
        doc.font(15, True)
        doc.cell(text_w - 7 - 26, 7, doc.text_ok(it["title"]))
        doc.set_fill_color(*TINT_RGB[st])
        doc.font(8, True, STATUS_RGB[st])
        doc.cell(26, 6, STATUS_WORD[st].upper(), align="C", fill=True, new_x="LEFT", new_y="NEXT")
        doc.set_xy(text_x, y + 8)
        if v:
            doc.font(11, True)
            doc.para(text_w, 5.5, _cap(v.get("label", "")))
        doc.set_x(text_x)
        doc.font(9.5, color=MUTED)
        doc.para(text_w, 4.6, v.get("summary", "") if v else "Not analyzed yet: press Re-analyze in the app.")
        doc.ln(2)

        # Readings: status dot, label, value, note with the green/red limits.
        for r in rows:
            ry = doc.get_y() + 0.8
            rs = r.get("status", "ok")
            doc.set_draw_color(*LINE)
            doc.line(text_x, ry - 0.8, PAGE_W - MARGIN, ry - 0.8)
            doc.set_fill_color(*STATUS_RGB.get(rs, MUTED))
            doc.ellipse(text_x, ry + 1.1, 2.2, 2.2, style="F")
            h_row = _row_height(doc, r, text_w, lab_w, val_w)
            doc.set_xy(text_x + 4, ry)
            doc.font(8.5, True)
            doc.para(lab_w - 6, 4, r.get("label", ""))
            doc.set_xy(text_x + lab_w, ry)
            doc.para(val_w - 2, 4, r.get("value", ""))
            doc.set_xy(text_x + lab_w + val_w, ry)
            doc.font(8.5, color=MUTED)
            doc.para(text_w - lab_w - val_w, 4, _note_text(r))
            doc.set_xy(text_x, ry + h_row + 1.4)

        if tip:
            doc.ln(1)
            ty = doc.get_y()
            doc.set_x(text_x + 4)
            doc.font(7.5, True, STATUS_RGB[st])
            doc.cell(0, 4.5, "HOW TO FIX" if st == "flag" else "WHAT TO TRY", new_x="LEFT", new_y="NEXT")
            doc.set_x(text_x + 4)
            doc.font(9.5)
            doc.para(text_w - 4, 4.6, tip)
            doc.set_fill_color(*STATUS_RGB[st])
            doc.rect(text_x, ty, 1, doc.get_y() - ty, style="F")

        doc.set_y(max(doc.get_y(), y + img_h) + 4)

    # How to read it, plus any notes about the clip.
    notes = [
        "The magenta line on each frame is the swing plane: the club shaft's line at address. The two grey "
        "lines either side mark the on-plane zone.",
        "On the frames, green / yellow / red marks what was measured, white dashed lines are targets or "
        "where you were at address, and cyan is an earlier checkpoint. Circle = clubhead, square = hands, "
        "ring = ball or another spot.",
        "Each measurement lists its Good range and its Fix range; anything in between is Watch (yellow).",
        f"Distances are rough estimates in centimetres, scaled from a typical {torso_cm:g} cm torso.",
    ] + list(analysis.get("warnings", [])) + [
        "Results are automatic estimates from video, for practice only: not professional coaching or medical "
        "advice. Practice safely, and see a coach or doctor before changing your swing if you have pain or an injury.",
    ]
    doc.font(8.5)
    need = 12 + sum(doc.para(CONTENT_W - 4, 4.2, n, dry=True) + 1.5 for n in notes)
    if doc.get_y() + need > doc.h - 18:
        doc.add_page()
    doc.set_draw_color(*LINE)
    doc.line(MARGIN, doc.get_y(), PAGE_W - MARGIN, doc.get_y())
    doc.ln(4)
    doc.font(11, True)
    doc.cell(0, 6, "How to read this", new_x="LMARGIN", new_y="NEXT")
    for n in notes:
        doc.font(8.5, color=MUTED)
        doc.cell(4, 4.2, "-")
        doc.para(CONTENT_W - 4, 4.2, n)
        doc.set_x(MARGIN)
        doc.ln(1.5)
    return bytes(doc.output())


def summary_pdf_for_run(folder: Path, swing_name: str, created: str, torso_cm: float = 50) -> bytes:
    analysis = json.loads((folder / "analysis.json").read_text())
    return summary_pdf(folder, swing_name, created, analysis, torso_cm)
