"""Single video frames as JPEG, for the marking screen's frame scrubber."""

from __future__ import annotations

import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path

import cv2


@dataclass
class _Open:
    """One open video. Its lock covers seeking and reading, so two visitors scrubbing
    different videos don't wait for each other."""
    cap: cv2.VideoCapture
    mtime: float
    next_index: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)
    closed: bool = False

    def close(self) -> None:
        with self.lock:  # waits for a read in progress to finish
            self.closed = True
            self.cap.release()


class FrameReader:
    """Keeps a few videos open so scrubbing doesn't reopen the file for every frame."""

    def __init__(self, max_open: int = 8):
        self._open_videos: OrderedDict[Path, _Open] = OrderedDict()
        self._lock = threading.Lock()  # guards the dict only, never held while reading
        self._max_open = max_open

    def jpeg(self, video: Path, index: int, width: int | None = None, quality: int = 85) -> bytes:
        while True:
            entry = self._get(video)
            with entry.lock:
                if entry.closed:  # closed (evicted or forgotten) after _get: open it again
                    continue
                if index != entry.next_index:
                    entry.cap.set(cv2.CAP_PROP_POS_FRAMES, index)
                ok, frame = entry.cap.read()
                entry.next_index = index + 1 if ok else -1
            break
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
            entry = self._open_videos.pop(video.resolve(), None)
        if entry:
            entry.close()

    def _get(self, video: Path) -> _Open:
        key = video.resolve()
        mtime = key.stat().st_mtime
        to_close = []
        with self._lock:
            entry = self._open_videos.get(key)
            if entry and entry.mtime != mtime:  # file was replaced (re-converted)
                to_close.append(self._open_videos.pop(key))
                entry = None
            if entry is None:
                cap = cv2.VideoCapture(str(key))
                if not cap.isOpened():
                    raise FileNotFoundError(str(video))
                entry = self._open_videos[key] = _Open(cap, mtime)
                while len(self._open_videos) > self._max_open:
                    to_close.append(self._open_videos.popitem(last=False)[1])
            self._open_videos.move_to_end(key)
        for old in to_close:  # outside the dict lock: closing waits for any read in progress
            old.close()
        return entry
