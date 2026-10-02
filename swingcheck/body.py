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
    """(frames, 2) hand position fused from both wrists.

    Both hands are on the grip, so the wrists should be close together:
    - wrists agree: their mean;
    - only one wrist detected: it stands in if visible enough;
    - wrists disagree (one mis-tracked; visibility is not a reliable guide
      to which): take the one that continues the hand path's recent motion;
    - a lone wrist that jumps far from where the path was heading is dropped
      and the gap is filled by interpolation.
    """
    pose_cfg = config["pose"]
    min_vis = pose_cfg["hand_min_visibility"]
    torso = _clip_torso_length(pose, config)
    max_sep = pose_cfg["hand_max_separation"] * torso
    max_jump = pose_cfg["hand_max_jump"] * torso

    left = pose.data[:, 15]   # left_wrist
    right = pose.data[:, 16]  # right_wrist
    out = np.full((len(pose), 2), np.nan)
    window = max(2, int(round(pose_cfg["hand_velocity_window_ms"] * pose.fps / 1000)))
    # Half the right-minus-left wrist offset from the last frame they agreed.
    # Adding it back when only one wrist is used keeps the estimate of the
    # midpoint continuous instead of snapping by half the wrist separation.
    # Updated only while the wrists are clearly together, and smoothly, so a
    # wrist that has started to drift doesn't leak into it.
    half: np.ndarray | None = None
    for i in range(len(pose)):
        # Low-visibility wrists stay in as candidates: a "hidden" wrist is often
        # still right while the visible one drifts (seen in DTL backswings).
        lw, rw = left[i], right[i]
        has_l, has_r = bool(np.isfinite(lw[0])), bool(np.isfinite(rw[0]))
        prediction = _predict(out, i, window)
        sep = float(np.linalg.norm(lw[:2] - rw[:2])) if has_l and has_r else np.inf
        if sep <= max_sep:
            # Plain mean: weighting by visibility would let a confidently
            # mis-tracked wrist drag the hands along before it's caught.
            out[i] = (lw[:2] + rw[:2]) / 2
            if sep <= max_sep / 2:
                current = (rw[:2] - lw[:2]) / 2
                half = current if half is None else 0.8 * half + 0.2 * current
        else:
            offset = half if half is not None else np.zeros(2)
            if has_l and has_r:
                from_l, from_r = lw[:2] + offset, rw[:2] - offset
                if prediction is not None:
                    out[i] = min((from_l, from_r), key=lambda c: np.linalg.norm(c - prediction))
                else:
                    out[i] = from_l if lw[3] >= rw[3] else from_r
            elif has_l and lw[3] >= min_vis:
                out[i] = lw[:2] + offset
            elif has_r and rw[3] >= min_vis:
                out[i] = rw[:2] - offset
        if prediction is not None and np.all(np.isfinite(out[i])) and np.linalg.norm(out[i] - prediction) > max_jump:
            out[i] = np.nan
    return clean_track(out, pose.fps, pose_cfg["max_gap_ms"], pose_cfg["smoothing_ms"])


def _predict(track: np.ndarray, i: int, window: int) -> np.ndarray | None:
    """Where the track should be at frame i: last known point plus its velocity
    averaged over the last `window` frames (a longer baseline resists a few bad frames)."""
    known = [j for j in range(max(0, i - 2 * window), i) if np.all(np.isfinite(track[j]))]
    if not known:
        return None
    last = known[-1]
    earlier = [j for j in known if last - j >= window] or known[:1]
    first = earlier[-1]
    if first == last:
        return track[last]
    velocity = (track[last] - track[first]) / (last - first)
    return track[last] + velocity * (i - last)


def _clip_torso_length(pose: PoseSeq, config: dict[str, Any]) -> float:
    a = midpoint(pose, "left_shoulder", "right_shoulder", config)
    b = midpoint(pose, "left_hip", "right_hip", config)
    lengths = np.linalg.norm(a - b, axis=1)
    value = float(np.nanmedian(lengths)) if np.isfinite(lengths).any() else float("nan")
    # Without a torso, fall back to a fraction of frame height.
    return value if np.isfinite(value) and value > 0 else pose.height / 5


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
