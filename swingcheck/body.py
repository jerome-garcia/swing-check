"""Body-derived tracks and measures shared by phase detection and analyzers."""

from __future__ import annotations

from typing import Any

import numpy as np

from swingcheck.models import PoseSeq
from swingcheck.pose import clean_track


def cleaned(pose: PoseSeq, name: str, config: dict[str, Any], min_visibility: float | None = None) -> np.ndarray:
    """One landmark's (frames, 2) track, low-visibility points dropped, gaps filled, smoothed."""
    pose_cfg = config["pose"]
    vis = pose_cfg["min_visibility"] if min_visibility is None else min_visibility
    return clean_track(pose.xy(name, vis), pose.fps, pose_cfg["max_gap_ms"], pose_cfg["smoothing_ms"])


def midpoint(pose: PoseSeq, a: str, b: str, config: dict[str, Any]) -> np.ndarray:
    return (cleaned(pose, a, config) + cleaned(pose, b, config)) / 2


def hands(pose: PoseSeq, config: dict[str, Any]) -> np.ndarray:
    """(frames, 2) hand position: visibility-weighted mean of both wrists.

    Both hands are on the grip, so when one wrist is hidden (often the lead
    wrist in DTL) the other stands in for both instead of leaving a gap.
    """
    pose_cfg = config["pose"]
    min_vis = pose_cfg["hand_min_visibility"]
    left = pose.data[:, 15]   # left_wrist
    right = pose.data[:, 16]  # right_wrist
    wl = np.where(left[:, 3] >= min_vis, left[:, 3], 0.0)
    wr = np.where(right[:, 3] >= min_vis, right[:, 3], 0.0)
    wl = np.nan_to_num(wl)
    wr = np.nan_to_num(wr)
    total = wl + wr
    with np.errstate(invalid="ignore", divide="ignore"):
        xy = (np.nan_to_num(left[:, :2]) * wl[:, None] + np.nan_to_num(right[:, :2]) * wr[:, None]) / total[:, None]
    xy[total == 0] = np.nan
    return clean_track(xy, pose.fps, pose_cfg["max_gap_ms"], pose_cfg["smoothing_ms"])


def body_scale(pose: PoseSeq, frame: int, config: dict[str, Any]) -> float:
    """Stable body length in pixels, measured around `frame` (normally address).

    Takes the median over a short window around the frame so one noisy
    detection doesn't skew every measurement.
    """
    method = config["scale"]["method"]
    if method == "torso":
        a = midpoint(pose, "left_shoulder", "right_shoulder", config)
        b = midpoint(pose, "left_hip", "right_hip", config)
    elif method == "shoulder_width":
        a = cleaned(pose, "left_shoulder", config)
        b = cleaned(pose, "right_shoulder", config)
    else:
        raise ValueError(f"scale.method must be 'torso' or 'shoulder_width', not {method!r}")
    lengths = np.linalg.norm(a - b, axis=1)
    half = max(1, int(round(pose.fps * config["scale"]["window_ms"] / 1000 / 2)))
    window = lengths[max(0, frame - half) : frame + half + 1]
    value = float(np.nanmedian(window)) if np.isfinite(window).any() else float("nan")
    if not np.isfinite(value) or value <= 0:
        # Fall back to the whole clip rather than failing outright.
        value = float(np.nanmedian(lengths))
    if not np.isfinite(value) or value <= 0:
        raise ValueError("Could not measure body scale: shoulders/hips not detected.")
    return value
