"""Shared data types passed between pipeline stages."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

Point = tuple[float, float]  # (x, y) in normalized-video pixel coordinates

# MediaPipe Pose's 33 landmarks, in index order.
LANDMARKS: tuple[str, ...] = (
    "nose", "left_eye_inner", "left_eye", "left_eye_outer", "right_eye_inner", "right_eye",
    "right_eye_outer", "left_ear", "right_ear", "mouth_left", "mouth_right",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow", "left_wrist", "right_wrist",
    "left_pinky", "right_pinky", "left_index", "right_index", "left_thumb", "right_thumb",
    "left_hip", "right_hip", "left_knee", "right_knee", "left_ankle", "right_ankle",
    "left_heel", "right_heel", "left_foot_index", "right_foot_index",
)
LANDMARK_INDEX = {name: i for i, name in enumerate(LANDMARKS)}

# Body-only skeleton edges for drawing (face and finger points left out).
SKELETON_EDGES: tuple[tuple[str, str], ...] = (
    ("left_shoulder", "right_shoulder"), ("left_hip", "right_hip"),
    ("left_shoulder", "left_hip"), ("right_shoulder", "right_hip"),
    ("left_shoulder", "left_elbow"), ("left_elbow", "left_wrist"),
    ("right_shoulder", "right_elbow"), ("right_elbow", "right_wrist"),
    ("left_hip", "left_knee"), ("left_knee", "left_ankle"), ("left_ankle", "left_foot_index"),
    ("right_hip", "right_knee"), ("right_knee", "right_ankle"), ("right_ankle", "right_foot_index"),
)


@dataclass
class PoseSeq:
    """Per-frame pose keypoints for one clip.

    `data` has shape (frames, 33, 4): x and y in normalized-video pixels, MediaPipe's
    relative depth z, and visibility (0-1). Frames with no detected person are all NaN.
    """

    fps: float
    width: int
    height: int
    data: np.ndarray
    # First/last frame where pose ran on every frame (auto-trim); None = unknown.
    dense: tuple[int, int] | None = None

    def __len__(self) -> int:
        return self.data.shape[0]

    def xy(self, name: str, min_visibility: float = 0.0) -> np.ndarray:
        """(frames, 2) track for one landmark; NaN where missing or below `min_visibility`."""
        lm = self.data[:, LANDMARK_INDEX[name]]
        xy = lm[:, :2].copy()
        with np.errstate(invalid="ignore"):
            xy[~(lm[:, 3] >= min_visibility)] = np.nan
        return xy

    def detected(self) -> np.ndarray:
        """Boolean mask of frames where a person was found."""
        return ~np.isnan(self.data[:, 0, 0])

# Points the user clicks on the address frame, in click order, per view.
REQUIRED_MARKS: dict[str, tuple[str, ...]] = {
    "dtl": ("ball", "clubhead", "grip"),
    "fo": ("ball",),
}

# Optional marks on later checkpoint frames (the pose model can't see the club),
# keyed by checkpoint: the points clicked there.
CHECKPOINT_MARKS: dict[str, dict[str, tuple[str, ...]]] = {
    "dtl": {"takeaway": ("clubhead", "grip"), "halfway_back": ("clubhead", "grip"), "top": ("clubhead", "grip"),
            "downswing": ("clubhead", "grip")},
    "fo": {},
}


@dataclass
class CheckpointMark:
    """Points clicked on one checkpoint's frame, e.g. the takeaway."""

    frame: int
    points: dict[str, Point]


@dataclass
class Marks:
    view: str
    address_frame: int
    points: dict[str, Point]
    # Identifies the normalized video the marks were made on, so a re-trim or
    # re-encode invalidates them instead of silently misplacing points.
    video_signature: dict[str, float | int | None] = field(default_factory=dict)
    # Optional marks on later frames, e.g. {"takeaway": CheckpointMark(...)}.
    checkpoints: dict[str, CheckpointMark] = field(default_factory=dict)

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(asdict(self), indent=2))

    @classmethod
    def load(cls, path: Path) -> "Marks":
        data = json.loads(path.read_text())
        data["points"] = _points(data["points"])
        data["checkpoints"] = {
            name: CheckpointMark(frame=int(cp["frame"]), points=_points(cp["points"]))
            for name, cp in (data.get("checkpoints") or {}).items()
        }
        return cls(**data)

    def checkpoint(self, name: str) -> CheckpointMark | None:
        """A checkpoint's marks, if all of its points were clicked."""
        cp = self.checkpoints.get(name)
        needed = CHECKPOINT_MARKS.get(self.view, {}).get(name, ())
        return cp if cp is not None and all(p in cp.points for p in needed) else None

    def is_complete(self) -> bool:
        return all(name in self.points for name in REQUIRED_MARKS[self.view])


def _points(raw: dict) -> dict[str, Point]:
    return {k: (float(v[0]), float(v[1])) for k, v in raw.items()}
