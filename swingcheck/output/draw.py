"""Drawing primitives for annotated frames, scaled to the video's resolution."""

from __future__ import annotations

from collections.abc import Sequence

import cv2
import numpy as np

from swingcheck.geometry import line_in_frame, ray_in_frame

FONT = cv2.FONT_HERSHEY_SIMPLEX


def ui_scale(height: int) -> float:
    """1.0 for 1280-px-tall (720p portrait) video; text and lines scale with it."""
    return max(0.5, height / 1280)


def header_clearance(s: float, lines: int = 2) -> int:
    """Lowest y a label should start at to clear a verdict header of `lines` rows."""
    return int(24 * s) * lines + int(30 * s)


def draw_text(img: np.ndarray, text: str, org: tuple[int, int], scale: float = 0.55,
              color: tuple[int, int, int] = (255, 255, 255), thickness: int = 1) -> None:
    """Text with a dark outline. The outline is drawn as offset copies at the same
    thickness: in OpenCV 5 a thicker stroke also widens glyph spacing."""
    x, y = org
    for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1), (0, 2), (2, 0)):
        cv2.putText(img, text, (x + dx, y + dy), FONT, scale, (0, 0, 0), thickness, cv2.LINE_AA)
    cv2.putText(img, text, org, FONT, scale, color, thickness, cv2.LINE_AA)


def text_size(text: str, scale: float, thickness: int = 1) -> tuple[int, int]:
    (w, h), _ = cv2.getTextSize(text, FONT, scale, thickness)
    return w, h


def panel(img: np.ndarray, top_left: tuple[int, int], bottom_right: tuple[int, int], alpha: float = 0.55) -> None:
    """Darken a rectangle so text on it stays readable."""
    x0, y0 = max(0, top_left[0]), max(0, top_left[1])
    x1, y1 = min(img.shape[1], bottom_right[0]), min(img.shape[0], bottom_right[1])
    if x1 <= x0 or y1 <= y0:
        return
    roi = img[y0:y1, x0:x1]
    img[y0:y1, x0:x1] = (roi * (1 - alpha)).astype(img.dtype)


def _pt(p: Sequence[float]) -> tuple[int, int]:
    return int(round(p[0])), int(round(p[1]))


def draw_line_overlay(img, kind: str, points, color, thickness: int, label: str, s: float, label_slot: int = 0,
                      ring: bool = False) -> None:
    """Draw one overlay. `thickness` is already scaled to the video; `ring` draws a point as a
    hollow reference marker (decided from the overlay's own style, not the scaled thickness)."""
    h, w = img.shape[:2]
    if kind in ("line", "ray"):
        o, through = np.asarray(points[0], float), np.asarray(points[1], float)
        fn = line_in_frame if kind == "line" else ray_in_frame
        seg = fn(o, through - o, w, h)
        if seg is None:
            return
        cv2.line(img, seg[0], seg[1], color, thickness, cv2.LINE_AA)
        if label:
            # Label near the far end, nudged inside the frame.
            end = np.asarray(seg[1], float)
            tw, th = text_size(label, 0.5 * s)
            x = int(np.clip(end[0] + 6, 4, w - tw - 4))
            # Keep clear of the verdict header at the top of the frame.
            y = int(np.clip(end[1] + th + 6 + label_slot * (th + 8), header_clearance(s), h - 4))
            draw_text(img, label, (x, y), 0.5 * s, color)
    elif kind == "segment":
        cv2.line(img, _pt(points[0]), _pt(points[1]), color, thickness, cv2.LINE_AA)
    elif kind == "dashed":
        a, b = np.asarray(points[0], float), np.asarray(points[1], float)
        length = float(np.linalg.norm(b - a))
        dash = max(6.0, 12.0 * s)
        for t0 in np.arange(0.0, length, 2 * dash):
            p0 = a + (b - a) * (t0 / length)
            p1 = a + (b - a) * (min(t0 + dash, length) / length)
            cv2.line(img, _pt(p0), _pt(p1), (0, 0, 0), thickness + 2, cv2.LINE_AA)
            cv2.line(img, _pt(p0), _pt(p1), color, thickness, cv2.LINE_AA)
        if label:
            draw_text(img, label, (_pt(b)[0] + 6, _pt(b)[1]), 0.45 * s, color)
    elif kind == "polyline":
        pts = [p for p in points if np.all(np.isfinite(p))]
        if len(pts) >= 2:
            arr = np.array([_pt(p) for p in pts], np.int32).reshape(-1, 1, 2)
            cv2.polylines(img, [arr], False, (0, 0, 0), thickness + 2, cv2.LINE_AA)
            cv2.polylines(img, [arr], False, color, thickness, cv2.LINE_AA)
    elif kind == "vline":
        # One point: full-height line at its x. Two points: vertical span from
        # points[0].y to points[1].y at points[0].x, labeled at its top.
        x = int(round(points[0][0]))
        if len(points) >= 2:
            y0, y1 = sorted((int(round(points[0][1])), int(round(points[1][1]))))
        else:
            y0, y1 = 0, h - 1
        cv2.line(img, (x, y0), (x, y1), (0, 0, 0), thickness + 2, cv2.LINE_AA)
        cv2.line(img, (x, y0), (x, y1), color, thickness, cv2.LINE_AA)
        if label:
            tw, th = text_size(label, 0.45 * s)
            y = y0 - 6 if len(points) >= 2 else int(h * 0.62) + label_slot * (th + 10)
            draw_text(img, label, (min(max(4, x + 5), w - tw - 4), max(th + 2, y)), 0.45 * s, color)
    elif kind == "point":
        r = max(4, int(round(7 * s)))
        if ring:
            # Thin points are reference markers (ball, address hands): draw a
            # ring so what's underneath stays visible.
            r = max(6, int(round(11 * s)))
            cv2.circle(img, _pt(points[0]), r, (0, 0, 0), 3, cv2.LINE_AA)
            cv2.circle(img, _pt(points[0]), r, color, 1, cv2.LINE_AA)
        else:
            cv2.circle(img, _pt(points[0]), r + 2, (0, 0, 0), -1, cv2.LINE_AA)
            cv2.circle(img, _pt(points[0]), r, color, -1, cv2.LINE_AA)
        if label:
            p = _pt(points[0])
            draw_text(img, label, (p[0] + r + 6, p[1] + 5 + label_slot * int(18 * s)), 0.5 * s, color)
    elif kind in ("circle", "square", "ring"):
        # Marks (see swingcheck/analyzers/__init__.py): clubhead = solid circle, hands =
        # solid square, ball and other spots = hollow ring. A black edge and, on the
        # solid ones, a white rim keep them readable over lines of the same color.
        p = _pt(points[0])
        r = max(5, int(round(8 * s)))
        if kind == "circle":
            cv2.circle(img, p, r + 3, (0, 0, 0), -1, cv2.LINE_AA)
            cv2.circle(img, p, r + 1, (255, 255, 255), -1, cv2.LINE_AA)
            cv2.circle(img, p, r, color, -1, cv2.LINE_AA)
        elif kind == "square":
            h2 = max(4, int(round(r * 0.9)))
            cv2.rectangle(img, (p[0] - h2 - 3, p[1] - h2 - 3), (p[0] + h2 + 3, p[1] + h2 + 3), (0, 0, 0), -1)
            cv2.rectangle(img, (p[0] - h2 - 1, p[1] - h2 - 1), (p[0] + h2 + 1, p[1] + h2 + 1), (255, 255, 255), -1)
            cv2.rectangle(img, (p[0] - h2, p[1] - h2), (p[0] + h2, p[1] + h2), color, -1)
        else:
            r = max(6, int(round(10 * s)))
            cv2.circle(img, p, r, (0, 0, 0), 5, cv2.LINE_AA)
            cv2.circle(img, p, r, color, 2, cv2.LINE_AA)
        if label:
            draw_text(img, label, (p[0] + r + 6, p[1] + 5 + label_slot * int(18 * s)), 0.5 * s, color)
    elif kind == "text":
        draw_text(img, label, _pt(points[0]), 0.5 * s, color)
    else:
        raise ValueError(f"unknown overlay kind {kind!r}")


def draw_path(img, path: np.ndarray, upto: int, start: int, segments: list[tuple[int, int, tuple[int, int, int]]],
              thickness: int) -> None:
    """Polyline of path[start..upto], colored by which segment (first, last, color) each step falls in."""
    for i in range(max(start + 1, 1), upto + 1):
        a, b = path[i - 1], path[i]
        if not (np.all(np.isfinite(a)) and np.all(np.isfinite(b))):
            continue
        color = next((c for lo, hi, c in segments if lo < i <= hi), segments[-1][2] if segments else (255, 255, 255))
        cv2.line(img, _pt(a), _pt(b), color, thickness, cv2.LINE_AA)
