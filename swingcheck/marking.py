"""Click-to-mark window: pick the address frame and click the ball (and club in DTL).

The window opens scaled to fit the screen and can be resized by dragging its
edges; clicks are mapped back to full-resolution pixel coordinates. A
magnifier in the corner helps place points precisely.

Keys:
  a / d  or  left / right   step 1 frame
  A / D  or  up / down      step 10 frames
  left click                place the next point
  u  or  Backspace          undo last point
  Enter  or  Space          save (once all points are placed)
  Esc  or  q                cancel
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from swingcheck.ingest import VideoInfo
from swingcheck.models import REQUIRED_MARKS, Marks, Point

WINDOW = "swingcheck: mark points"

KEY_ENTER = (13, 10)
KEY_SPACE = 32
KEY_ESC = 27
KEY_BACKSPACE = 8
# cv2.waitKeyEx codes for arrow keys (Windows / GTK).
KEY_LEFT = (2424832, 65361)
KEY_RIGHT = (2555904, 65363)
KEY_UP = (2490368, 65362)
KEY_DOWN = (2621440, 65364)

MARK_COLORS = {"ball": (255, 255, 255), "clubhead": (0, 200, 255), "grip": (255, 120, 0)}
# Label offsets from the point (ball and clubhead sit next to each other at address).
LABEL_OFFSETS = {"ball": (9, 20), "clubhead": (-80, -10), "grip": (10, -8)}
# The shaft line runs clubhead -> grip, so the clubhead click belongs on the hosel.
CLICK_HINTS = {"clubhead": " (hosel)", "grip": " (center of hands)"}


class MarkingCancelled(RuntimeError):
    pass


def video_signature(info: VideoInfo) -> dict[str, float | int | None]:
    return {
        "width": info.width,
        "height": info.height,
        "fps": info.fps,
        "frame_count": info.frame_count,
        "trim_start": info.trim_start,
        "trim_end": info.trim_end,
    }


def load_marks(path: Path, view: str, info: VideoInfo) -> Marks | None:
    """Saved marks if they exist and still match this view and normalized video, else None."""
    if not path.exists():
        return None
    try:
        marks = Marks.load(path)
    except (KeyError, TypeError, ValueError):
        return None
    if marks.view != view or marks.video_signature != video_signature(info) or not marks.is_complete():
        return None
    return marks


def screen_work_area() -> tuple[int, int] | None:
    """Usable desktop size (excluding the taskbar) on Windows, else None."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        rect = wintypes.RECT()
        SPI_GETWORKAREA = 0x0030
        if ctypes.windll.user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0):
            return rect.right - rect.left, rect.bottom - rect.top
    except (AttributeError, OSError):
        pass
    return None


def display_limits(marking_cfg: dict[str, Any], work_area: tuple[int, int] | None = None) -> tuple[int, int]:
    """Max window size: a fraction of the screen's work area, capped by the config limits.

    A config limit of 0 means "no fixed cap, just fit the screen".
    """
    max_w = marking_cfg["max_display_width"] or 10**6
    max_h = marking_cfg["max_display_height"] or 10**6
    area = work_area if work_area is not None else screen_work_area()
    if area is not None:
        fraction = marking_cfg["screen_fraction"]
        # Leave room for the window title bar (~40px) below the fitted height.
        max_w = min(max_w, int(area[0] * fraction))
        max_h = min(max_h, int(area[1] * fraction) - 40)
    elif max_w >= 10**6 or max_h >= 10**6:
        max_w, max_h = min(max_w, 1280), min(max_h, 720)  # unknown screen: conservative default
    return max_w, max_h


def display_scale(width: int, height: int, max_width: int, max_height: int) -> float:
    """Factor (<= 1) that fits the frame inside the max display size."""
    return min(1.0, max_width / width, max_height / height)


@dataclass
class MarkSession:
    """UI-independent marking state, so the logic is testable without a window."""

    view: str
    frame_count: int
    frame: int = 0
    points: dict[str, Point] = field(default_factory=dict)

    @property
    def required(self) -> tuple[str, ...]:
        return REQUIRED_MARKS[self.view]

    @property
    def next_mark(self) -> str | None:
        for name in self.required:
            if name not in self.points:
                return name
        return None

    @property
    def complete(self) -> bool:
        return self.next_mark is None

    def step(self, delta: int) -> None:
        self.frame = max(0, min(self.frame_count - 1, self.frame + delta))

    def click(self, point: Point) -> None:
        name = self.next_mark
        if name is not None:
            self.points[name] = point

    def undo(self) -> None:
        for name in reversed(self.required):
            if name in self.points:
                del self.points[name]
                return


class _FrameReader:
    """Random-access frame reader that avoids re-seeking when stepping forward by one."""

    def __init__(self, path: Path):
        self.cap = cv2.VideoCapture(str(path))
        if not self.cap.isOpened():
            raise RuntimeError(f"OpenCV could not open {path}")
        self.next_index = 0
        self.cache: tuple[int, np.ndarray] | None = None

    def read(self, index: int) -> np.ndarray:
        if self.cache is not None and self.cache[0] == index:
            return self.cache[1]
        if index != self.next_index:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, frame = self.cap.read()
        if not ok:
            raise RuntimeError(f"Could not read frame {index}")
        self.next_index = index + 1
        self.cache = (index, frame)
        return frame

    def close(self) -> None:
        self.cap.release()


def _draw_text(img: np.ndarray, text: str, org: tuple[int, int], scale: float = 0.55) -> None:
    # Outline via offset copies at the same thickness: in OpenCV 5 a thicker
    # stroke also widens glyph spacing, so a thick-stroke outline doesn't line up.
    x, y = org
    for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        cv2.putText(img, text, (x + dx, y + dy), cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), 1, cv2.LINE_AA)
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, (255, 255, 255), 1, cv2.LINE_AA)


def _draw_magnifier(canvas: np.ndarray, frame: np.ndarray, center: Point, size: int, zoom: int) -> None:
    """Paste a zoomed crop of the full-res frame around `center` into the canvas corner away from it."""
    half = size // (2 * zoom)
    h, w = frame.shape[:2]
    cx = min(max(int(center[0]), 0), w - 1)
    cy = min(max(int(center[1]), 0), h - 1)
    padded = cv2.copyMakeBorder(frame, half, half, half, half, cv2.BORDER_CONSTANT)
    crop = padded[cy : cy + 2 * half, cx : cx + 2 * half]
    loupe = cv2.resize(crop, (size, size), interpolation=cv2.INTER_NEAREST)
    mid = size // 2
    cv2.line(loupe, (mid, 0), (mid, size), (0, 255, 255), 1)
    cv2.line(loupe, (0, mid), (size, mid), (0, 255, 255), 1)
    cv2.rectangle(loupe, (0, 0), (size - 1, size - 1), (255, 255, 255), 1)

    ch, cw = canvas.shape[:2]
    # Corner opposite the cursor so the loupe never covers what you're aiming at.
    left = cx > w / 2
    top = cy > h / 2
    x0 = 8 if left else cw - size - 8
    y0 = 54 if top else ch - size - 8
    canvas[y0 : y0 + size, x0 : x0 + size] = loupe


def _render(
    session: MarkSession, frame: np.ndarray, scale: float, cursor: Point | None, marking_cfg: dict[str, Any]
) -> np.ndarray:
    h, w = frame.shape[:2]
    canvas = cv2.resize(frame, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_AREA)

    for name, (x, y) in session.points.items():
        p = (round(x * scale), round(y * scale))
        color = MARK_COLORS.get(name, (0, 255, 0))
        cv2.circle(canvas, p, 6, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.circle(canvas, p, 6, color, 2, cv2.LINE_AA)
        dx, dy = LABEL_OFFSETS.get(name, (9, -9))
        _draw_text(canvas, name, (p[0] + dx, p[1] + dy), 0.5)
    if "clubhead" in session.points and "grip" in session.points:
        a = tuple(round(v * scale) for v in session.points["clubhead"])
        b = tuple(round(v * scale) for v in session.points["grip"])
        cv2.line(canvas, a, b, (0, 200, 255), 1, cv2.LINE_AA)

    if cursor is not None:
        _draw_magnifier(canvas, frame, cursor, marking_cfg["magnifier_size"], marking_cfg["magnifier_zoom"])

    nxt = session.next_mark
    action = f"click: {nxt.upper()}{CLICK_HINTS.get(nxt, '')}" if nxt else "press Enter to save"
    cv2.rectangle(canvas, (0, 0), (canvas.shape[1], 46), (40, 40, 40), -1)
    _draw_text(canvas, f"frame {session.frame + 1}/{session.frame_count}   {action}", (8, 19), 0.55)
    _draw_text(canvas, "a/d step  A/D x10  u undo  Esc cancel", (8, 39), 0.45)
    return canvas


def run_marking_ui(video_path: Path, view: str, info: VideoInfo, config: dict[str, Any], start_frame: int = 0) -> Marks:
    """Open the window, let the user mark points, return the Marks. Raises MarkingCancelled."""
    marking_cfg = config["marking"]
    reader = _FrameReader(video_path)
    frame_count = info.frame_count or int(reader.cap.get(cv2.CAP_PROP_FRAME_COUNT))
    session = MarkSession(view=view, frame_count=frame_count, frame=min(start_frame, frame_count - 1))
    max_w, max_h = display_limits(marking_cfg)
    scale = display_scale(info.width, info.height, max_w, max_h)
    state: dict[str, Any] = {"cursor": None, "dirty": True}

    def on_mouse(event: int, x: int, y: int, flags: int, param: Any) -> None:
        # In a resizable window OpenCV reports x/y in image (canvas) pixels,
        # whatever size the window has been dragged to.
        full = (x / scale, y / scale)
        if event == cv2.EVENT_MOUSEMOVE:
            state["cursor"] = full
            state["dirty"] = True
        elif event == cv2.EVENT_LBUTTONDOWN:
            session.click(full)
            state["dirty"] = True

    # Resizable, aspect-locked window starting at the fitted size.
    cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO)
    cv2.resizeWindow(WINDOW, round(info.width * scale), round(info.height * scale))
    cv2.moveWindow(WINDOW, 20, 10)
    cv2.setMouseCallback(WINDOW, on_mouse)
    try:
        while True:
            if state["dirty"]:
                frame = reader.read(session.frame)
                cv2.imshow(WINDOW, _render(session, frame, scale, state["cursor"], marking_cfg))
                state["dirty"] = False
            key = cv2.waitKeyEx(20)
            if cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
                raise MarkingCancelled("window closed")
            if key == -1:
                continue
            state["dirty"] = True
            ch = chr(key) if 0 <= key < 256 else ""
            if key == KEY_ESC or ch == "q":
                raise MarkingCancelled("cancelled")
            elif key in KEY_ENTER or key == KEY_SPACE:
                if session.complete:
                    break
            elif ch == "u" or key == KEY_BACKSPACE:
                session.undo()
            elif ch == "a" or key in KEY_LEFT:
                session.step(-1)
            elif ch == "d" or key in KEY_RIGHT:
                session.step(1)
            elif ch == "A" or key in KEY_UP:
                session.step(-10)
            elif ch == "D" or key in KEY_DOWN:
                session.step(10)
    finally:
        reader.close()
        cv2.destroyWindow(WINDOW)
        cv2.waitKey(1)

    return Marks(
        view=view,
        address_frame=session.frame,
        points=dict(session.points),
        video_signature=video_signature(info),
    )


def get_marks(
    video_path: Path, run_dir: Path, view: str, info: VideoInfo, config: dict[str, Any], remark: bool = False
) -> tuple[Marks, bool]:
    """Saved marks if valid (and not `remark`), else open the UI and save. Returns (marks, reused)."""
    path = run_dir / "marks.json"
    previous = None if remark else load_marks(path, view, info)
    if previous is not None:
        return previous, True
    # Start on the previously chosen frame when re-marking.
    start = 0
    if path.exists():
        try:
            start = Marks.load(path).address_frame
        except (KeyError, TypeError, ValueError):
            pass
    marks = run_marking_ui(video_path, view, info, config, start_frame=start)
    marks.save(path)
    return marks, False
