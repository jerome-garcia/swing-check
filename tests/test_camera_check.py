"""Camera check: a clean down-the-line view passes; the usual filming mistakes are named."""

import numpy as np

from swingcheck.camera_check import camera_check
from swingcheck.config import load_config
from swingcheck.models import LANDMARK_INDEX, LANDMARKS, PoseSeq

W, H = 1080, 1920

# A right-handed golfer at address seen from behind the hands: facing right (nose ahead
# of the hips), shoulders and hips overlapping left to right, filling ~40% of the height.
DTL = {
    "nose": (640, 760), "left_ear": (600, 740), "right_ear": (610, 745),
    "left_shoulder": (560, 820), "right_shoulder": (575, 825),
    "left_hip": (470, 1110), "right_hip": (480, 1115),
    "left_knee": (520, 1330), "right_knee": (530, 1335),
    "left_ankle": (480, 1520), "right_ankle": (490, 1525),
    "left_heel": (470, 1535), "right_heel": (480, 1540),
    "left_wrist": (640, 1130), "right_wrist": (650, 1135),
}


def pose_of(points, frames=10, visibility=0.95):
    data = np.full((frames, len(LANDMARKS), 4), np.nan)
    for name, (x, y) in points.items():
        data[:, LANDMARK_INDEX[name]] = (x, y, 0.0, visibility)
    return PoseSeq(30.0, W, H, data)


def titles(points, **kw):
    return [f["title"] for f in camera_check(pose_of(points, **kw), 5, load_config())]


def spread_by(dx):
    """Shoulders and hips pulled apart left to right by +-dx: the camera off to the side."""
    p = dict(DTL)
    for part in ("shoulder", "hip"):
        lx, ly = p[f"left_{part}"]
        rx, ry = p[f"right_{part}"]
        mid = (lx + rx) / 2
        p[f"left_{part}"], p[f"right_{part}"] = (mid - dx, ly), (mid + dx, ry)
    return p


def test_a_clean_down_the_line_view_passes():
    assert titles(DTL) == []


def test_face_on_or_angled_cameras_are_named():
    assert titles(spread_by(110)) == ["This doesn't look like a down-the-line view"]  # ~0.75 torso: face-on
    assert titles(spread_by(60)) == ["The camera may be off to one side"]             # ~0.41 torso


def test_facing_the_wrong_way():
    mirrored = {k: (W - x, y) for k, (x, y) in DTL.items()}
    assert titles(mirrored) == ["You're facing left"]


def test_framing_problems():
    small = {k: (540 + (x - 540) * 0.4, 960 + (y - 960) * 0.4) for k, (x, y) in DTL.items()}
    assert titles(small) == ["You're small in the frame"]
    cut = {k: (x, y + 420) for k, (x, y) in DTL.items()}  # feet below the frame
    assert titles(cut) == ["Your feet are cut off or hidden"]
    high = {k: (x, y - 750) for k, (x, y) in DTL.items()}  # head above the frame
    assert "Your head is cut off" in titles(high)


def test_hard_to_see_and_no_golfer():
    assert titles(DTL, visibility=0.3) == ["Your feet are cut off or hidden", "Your body is hard to see"]
    assert titles({}) == ["No golfer found"]


def test_far_leg_hidden_behind_the_near_one_is_fine():
    data = pose_of(DTL).data
    for name in ("left_ankle", "left_knee", "left_heel"):  # the lead leg, hidden from behind
        data[:, LANDMARK_INDEX[name], 3] = 0.2
    assert camera_check(PoseSeq(30.0, W, H, data), 5, load_config()) == []
