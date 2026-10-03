"""Single video frames as JPEG, for the marking screen's frame scrubber."""

from __future__ import annotations

import threading
from collections import OrderedDict
from pathlib import Path

import cv2


class FrameReader:
    """Keeps a few videos open so scrubbing doesn't reopen the file for every frame."""

    def __init__(self, max_open: int = 4):
        self._caps: OrderedDict[Path, tuple[cv2.VideoCapture, float, list[int]]] = OrderedDict()
        self._lock = threading.Lock()
        self._max_open = max_open

    def jpeg(self, video: Path, index: int, width: int | None = None, quality: int = 85) -> bytes:
        with self._lock:
            cap, next_index = self._open(video)
            if index != next_index[0]:
                cap.set(cv2.CAP_PROP_POS_FRAMES, index)
            ok, frame = cap.read()
            next_index[0] = index + 1 if ok else -1
        if not ok:
            raise IndexError(f"frame {index} not available")
        if width and width < frame.shape[1]:
            h = round(frame.shape[0] * width / frame.shape[1])
            frame = cv2.resize(frame, (width, h), interpolation=cv2.INTER_AREA)
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
        if not ok:
            raise RuntimeError("could not encode frame")
        return buf.tobytes()

    def forget(self, video: Path) -> None:
        """Close a video (e.g. before it's re-converted or deleted)."""
        with self._lock:
            entry = self._caps.pop(video.resolve(), None)
            if entry:
                entry[0].release()

    def _open(self, video: Path) -> tuple[cv2.VideoCapture, list[int]]:
        key = video.resolve()
        mtime = key.stat().st_mtime
        entry = self._caps.get(key)
        if entry and entry[1] != mtime:  # file was replaced (re-converted)
            entry[0].release()
            entry = None
        if entry is None:
            cap = cv2.VideoCapture(str(key))
            if not cap.isOpened():
                raise FileNotFoundError(str(video))
            entry = (cap, mtime, [0])
            self._caps[key] = entry
            while len(self._caps) > self._max_open:
                _, (old, _, _) = self._caps.popitem(last=False)
                old.release()
        self._caps.move_to_end(key)
        return entry[0], entry[2]
