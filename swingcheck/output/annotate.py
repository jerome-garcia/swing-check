"""Annotated video, freeze-frame images and a side-by-side summary image.

Everything an analyzer wants drawn comes from its Verdict.overlays, so new
analyzers show up here without changes. This module adds the shared parts:
the hand-path trail (off by default, see [output] show_hand_path), phase labels,
and a header listing each verdict.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from swingcheck.analyzers import STATUS_COLORS, Overlay, Verdict
from swingcheck.output.draw import (
    draw_line_overlay,
    draw_path,
    draw_text,
    header_clearance,
    panel,
    text_size,
    ui_scale,
)
from swingcheck.output.video import VideoWriter, iter_frames
from swingcheck.phases import PHASE_NAMES, Phases

BACKSWING_COLOR = (255, 200, 60)
DOWNSWING_COLOR = (200, 80, 255)
FOLLOW_COLOR = (170, 170, 170)
PHASE_LABEL_HOLD_MS = 250


class Annotator:
    def __init__(self, verdicts: list[Verdict], phases: Phases, hands: np.ndarray, fps: float,
                 width: int, height: int, config: dict[str, Any]):
        self.verdicts = verdicts
        self.phases = phases
        self.fps = fps
        self.s = ui_scale(height)
        self.out_cfg = config["output"]
        self.overlays: list[Overlay] = [o for v in verdicts for o in v.overlays if o.kind != "path"]
        # An analyzer-supplied path (e.g. calibrated hands) replaces the raw wrist trail.
        supplied = [o for v in verdicts for o in v.overlays if o.kind == "path"]
        self.path = np.asarray(supplied[0].points, float) if supplied else np.asarray(hands, float)
        trail_ms = self.out_cfg["trail_length_ms"]
        self.trail_frames = int(round(trail_ms * fps / 1000)) if trail_ms > 0 else None
        self.segments = [
            (phases.address, phases.top, BACKSWING_COLOR),
            (phases.top, phases.impact, DOWNSWING_COLOR),
            (phases.impact, len(self.path) - 1, FOLLOW_COLOR),
        ]

    def only(self, verdict: Verdict) -> "Annotator":
        """A copy that draws just this verdict (its overlays and header line), for its key frame."""
        clone = copy.copy(self)
        clone.verdicts = [verdict]
        clone.overlays = [o for o in verdict.overlays if o.kind != "path"]
        return clone

    def segment_name(self, i: int) -> str:
        p = self.phases
        if i < p.address:
            return "setup"
        if i < p.top:
            return "backswing"
        if i < p.impact:
            return "downswing"
        return "follow-through"

    def render(self, frame: np.ndarray, i: int, footer: str = "", big_label: str | None = None) -> np.ndarray:
        img = frame.copy()
        s = self.s
        thick = max(1, int(round(2 * s)))

        # Hand path from address (or the trail window) to now.
        if self.out_cfg["show_hand_path"] and i > self.phases.address:
            start = self.phases.address if self.trail_frames is None else max(self.phases.address, i - self.trail_frames)
            draw_path(img, self.path, min(i, len(self.path) - 1), start, self.segments, thick + 1)

        slots: dict[str, int] = {}
        for o in self.overlays:
            if o.frames is not None and not (o.frames[0] <= i <= o.frames[1]):
                continue
            slot = slots.get(o.kind, 0)
            slots[o.kind] = slot + 1
            draw_line_overlay(img, o.kind, o.points, o.color, max(1, int(round(o.thickness * s))), o.label, s, slot,
                              ring=o.thickness <= 1)

        active = self._active(i)
        self._header(img, active)
        label = big_label or self._phase_flash(i)
        if label:
            # Upper-right under the verdict header: clear of the golfer's head, and
            # of the plane-line labels that end up top-left for a right-hander in DTL.
            scale = 1.1 * s
            tw, th = text_size(label, scale, 2)
            x = img.shape[1] - tw - int(16 * s)
            y = header_clearance(s, max(1, len(active))) + th
            panel(img, (x - 12, y - th - 12), (x + tw + 12, y + 12), 0.5)
            draw_text(img, label, (x, y), scale, (255, 255, 255), 2)
        if footer:
            tw, th = text_size(footer, 0.5 * s)
            panel(img, (0, img.shape[0] - th - 18), (img.shape[1], img.shape[0]), 0.5)
            draw_text(img, footer, (8, img.shape[0] - 9), 0.5 * s)
        return img

    def _phase_flash(self, i: int) -> str | None:
        hold = max(1, int(round(PHASE_LABEL_HOLD_MS * self.fps / 1000)))
        for name in ("address", "top", "impact"):
            f = getattr(self.phases, name)
            if f <= i < f + hold:
                return name.upper()
        return None

    def _active(self, i: int) -> list[Verdict]:
        """Checks to name in the header on frame i: the one this annotator draws (a key frame),
        or, in the full video, those whose lines are on screen right now."""
        if len(self.verdicts) == 1:
            return list(self.verdicts)
        return [v for v in self.verdicts
                if any(o.kind != "path" and (o.frames is None or o.frames[0] <= i <= o.frames[1]) for o in v.overlays)]

    def _header(self, img: np.ndarray, verdicts: list[Verdict]) -> None:
        s = self.s
        line_h = int(24 * s)
        lines = [(f"{v.title}: {v.label}", STATUS_COLORS[v.status]) for v in verdicts]
        if not lines:
            return
        panel(img, (0, 0), (img.shape[1], line_h * len(lines) + int(10 * s)), 0.55)
        for k, (text, color) in enumerate(lines):
            y = int(8 * s) + line_h * (k + 1) - int(6 * s)
            r = max(3, int(5 * s))
            cv2.circle(img, (int(14 * s), y - r), r, color, -1, cv2.LINE_AA)
            draw_text(img, text, (int(26 * s), y), 0.55 * s)


def write_outputs(run_dir: Path, annotator: Annotator, frame_range: tuple[int, int], config: dict[str, Any],
                  video: bool = True) -> dict[str, Path]:
    """Annotated video over frame_range, freeze frames, and summary.png. Returns written paths."""
    out_cfg = config["output"]
    fps = annotator.fps
    playback = min(fps, out_cfg["max_playback_fps"])
    slow = fps / playback
    slow_note = f"  {slow:g}x slow" if slow > 1.01 else ""
    freeze_names = [n for n in out_cfg["freeze_frames"] if n in PHASE_NAMES]
    # frame -> images to save there: (file stem, annotator, big label, phase name for the footer)
    stills: dict[int, list[tuple[str, Annotator, str, str]]] = {}
    for n in freeze_names:
        stills.setdefault(getattr(annotator.phases, n), []).append((n, annotator, n.upper(), n))
    # Each check's own key frame, drawn with only its lines (shown in the app's checkpoint stepper).
    for v in annotator.verdicts:
        if v.status == "error":
            continue
        if v.frame is not None:
            stills.setdefault(v.frame, []).append((f"check_{v.name}", annotator.only(v), v.title.upper(), v.name))
        elif v.phase in PHASE_NAMES:
            stills.setdefault(getattr(annotator.phases, v.phase), []).append(
                (f"check_{v.name}", annotator.only(v), v.title.upper(), v.phase))
    last_still = max(stills, default=0)

    written: dict[str, Path] = {}
    freezes: dict[str, np.ndarray] = {}
    writer = None
    try:
        for i, frame in enumerate(iter_frames(run_dir / "normalized.mp4")):
            in_range = frame_range[0] <= i <= frame_range[1]
            if not in_range and i not in stills:
                if i > max(frame_range[1], last_still):
                    break
                continue
            footer = f"{annotator.segment_name(i)}   frame {i}   {i / fps:.3f}s{slow_note}"
            if video and in_range:
                if writer is None:
                    written["video"] = run_dir / "annotated.mp4"
                    writer = VideoWriter(written["video"], frame.shape[1], frame.shape[0], playback)
                writer.write(annotator.render(frame, i, footer))
            for stem, ann, big, phase in stills.get(i, []):
                img = ann.render(frame, i, f"{phase.replace('_', ' ')}   frame {i}   {i / fps:.3f}s", big_label=big)
                if stem in freeze_names:
                    freezes[stem] = img
                path = run_dir / f"{stem}.png"
                cv2.imwrite(str(path), img)
                written[stem] = path
    finally:
        if writer is not None:
            writer.close()

    if freezes:
        ordered = [freezes[n] for n in freeze_names if n in freezes]
        h = min(img.shape[0] for img in ordered)
        tiles = [cv2.resize(img, (round(img.shape[1] * h / img.shape[0]), h)) for img in ordered]
        sheet = np.hstack(tiles)
        if sheet.shape[0] > 1280:  # keep the summary a sensible size
            f = 1280 / sheet.shape[0]
            sheet = cv2.resize(sheet, (round(sheet.shape[1] * f), 1280), interpolation=cv2.INTER_AREA)
        written["summary"] = run_dir / "summary.png"
        cv2.imwrite(str(written["summary"]), sheet)
    return written
