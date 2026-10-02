"""2D geometry for swing measurements. Pure functions on pixel coordinates.

Image coordinates: x grows right, y grows down.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

Vec = np.ndarray  # shape (2,)


def as_vec(p) -> Vec:
    return np.asarray(p, dtype=float).reshape(2)


def unit(v) -> Vec:
    v = as_vec(v)
    n = np.linalg.norm(v)
    if n == 0 or not np.isfinite(n):
        raise ValueError("cannot normalize a zero or non-finite vector")
    return v / n


def normal(direction) -> Vec:
    """A unit normal to `direction` (rotated 90 degrees)."""
    d = unit(direction)
    return np.array([-d[1], d[0]])


def signed_distance(p, origin, direction) -> float:
    """Perpendicular distance from p to the line through origin along direction.

    Sign follows `normal(direction)`; only the sign's consistency matters to callers.
    """
    return float(np.dot(as_vec(p) - as_vec(origin), normal(direction)))


def to_body_units(px: float, scale_px: float) -> float:
    """Pixel length -> multiples of the body scale (e.g. torso length)."""
    if not scale_px > 0:
        raise ValueError(f"body scale must be positive, got {scale_px}")
    return px / scale_px


def along(vec, direction) -> float:
    """Component of `vec` along `direction` (signed, pixels)."""
    return float(np.dot(as_vec(vec), unit(direction)))


@dataclass
class WedgeResult:
    """Where a point sits relative to two lines from a shared origin.

    zone: "inside" (between the lines or within tolerance of one),
          "beyond_a" (outside, past line a), "beyond_b" (outside, past line b).
    margin_a / margin_b: signed distance into the wedge from each line, in
    pixels (positive = inside of that line).
    """

    zone: str
    margin_a: float
    margin_b: float


def inward_normal(direction, other_direction) -> Vec:
    """Unit normal to `direction` pointing toward the side `other_direction` heads into."""
    n = normal(direction)
    return n if np.dot(unit(other_direction), n) >= 0 else -n


def classify_in_wedge(p, origin, dir_a, dir_b, tolerance_px: float = 0.0) -> WedgeResult:
    """Classify point p against the wedge between line a and line b, both through `origin`.

    Each line's inside is the side the other line points into, so this is
    independent of image orientation and handedness. Being within
    `tolerance_px` past a line still counts as inside.
    """
    p, o = as_vec(p), as_vec(origin)
    if abs(np.dot(unit(dir_a), normal(dir_b))) < 1e-9:
        raise ValueError("the two lines are parallel; there is no wedge between them")
    n_a = inward_normal(dir_a, dir_b)
    n_b = inward_normal(dir_b, dir_a)

    margin_a = float(np.dot(p - o, n_a))
    margin_b = float(np.dot(p - o, n_b))
    past_a = margin_a < -tolerance_px
    past_b = margin_b < -tolerance_px
    if past_a and past_b:
        zone = "beyond_a" if margin_a < margin_b else "beyond_b"
    elif past_a:
        zone = "beyond_a"
    elif past_b:
        zone = "beyond_b"
    else:
        zone = "inside"
    return WedgeResult(zone=zone, margin_a=margin_a, margin_b=margin_b)


def angle_deg(direction) -> float:
    """Angle of a direction measured from the +x axis, counterclockwise as seen on screen (y up)."""
    d = as_vec(direction)
    return float(np.degrees(np.arctan2(-d[1], d[0])))


def line_in_frame(origin, direction, width: int, height: int) -> tuple[tuple[int, int], tuple[int, int]] | None:
    """Endpoints where the infinite line through origin/direction crosses the frame, for drawing.

    Returns None if the line misses the frame.
    """
    o, d = as_vec(origin), unit(direction)
    ts: list[float] = []
    for axis, limit in ((0, width - 1), (1, height - 1)):
        if abs(d[axis]) > 1e-12:
            for edge in (0.0, float(limit)):
                t = (edge - o[axis]) / d[axis]
                q = o + t * d
                if -1e-6 <= q[0] <= width - 1 + 1e-6 and -1e-6 <= q[1] <= height - 1 + 1e-6:
                    ts.append(t)
    if len(ts) < 2:
        return None
    a, b = o + min(ts) * d, o + max(ts) * d
    return (int(round(a[0])), int(round(a[1]))), (int(round(b[0])), int(round(b[1])))


def ray_in_frame(origin, direction, width: int, height: int) -> tuple[tuple[int, int], tuple[int, int]] | None:
    """Like line_in_frame but only the half starting at origin and heading along direction."""
    seg = line_in_frame(origin, direction, width, height)
    if seg is None:
        return None
    o, d = as_vec(origin), unit(direction)
    far = max(seg, key=lambda q: np.dot(as_vec(q) - o, d))
    if np.dot(as_vec(far) - o, d) <= 0:
        return None
    start = (int(round(o[0])), int(round(o[1])))
    return start, far


def target_sign(view: str, handedness: str, fo_override: str = "auto") -> int:
    """+1 if the target is toward screen-right in a face-on view, -1 if screen-left.

    Face-on with the camera facing the golfer: a right-hander's target is on
    screen-right. Only meaningful for "fo"; DTL looks along the target line.
    """
    if view != "fo":
        raise ValueError("target direction along x is only defined for the face-on view")
    if fo_override in ("left", "right"):
        return 1 if fo_override == "right" else -1
    if fo_override != "auto":
        raise ValueError(f"target_direction_fo must be auto, left or right, not {fo_override!r}")
    if handedness not in ("right", "left"):
        raise ValueError(f"handedness must be right or left, not {handedness!r}")
    return 1 if handedness == "right" else -1
