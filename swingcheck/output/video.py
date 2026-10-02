"""Frame I/O helpers: iterate a video's frames, and write frames to an H.264 MP4 via ffmpeg.

Writing through ffmpeg (rather than cv2.VideoWriter) gives H.264 output that
plays in any player, including the Windows Photos app.
"""

from __future__ import annotations

import subprocess
from collections.abc import Iterator
from pathlib import Path

import cv2
import numpy as np

from swingcheck.ingest import find_tool


def iter_frames(path: Path) -> Iterator[np.ndarray]:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"OpenCV could not open {path}")
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                return
            yield frame
    finally:
        cap.release()


class VideoWriter:
    """Pipe BGR frames into ffmpeg. Use as a context manager."""

    def __init__(self, path: Path, width: int, height: int, fps: float, crf: int = 20):
        self.path = path
        cmd = [
            find_tool("ffmpeg"), "-v", "error", "-y",
            "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{width}x{height}", "-r", f"{fps:g}",
            "-i", "-",
            "-c:v", "libx264", "-preset", "fast", "-crf", str(crf), "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(path),
        ]
        self.size = (width, height)
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)

    def write(self, frame: np.ndarray) -> None:
        if (frame.shape[1], frame.shape[0]) != self.size:
            raise ValueError(f"frame is {frame.shape[1]}x{frame.shape[0]}, writer expects {self.size}")
        assert self.proc.stdin is not None
        self.proc.stdin.write(np.ascontiguousarray(frame).tobytes())

    def close(self) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.close()
        err = self.proc.stderr.read().decode(errors="replace") if self.proc.stderr else ""
        if self.proc.wait() != 0:
            raise RuntimeError(f"ffmpeg failed writing {self.path}: {err.strip()}")

    def __enter__(self) -> "VideoWriter":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
