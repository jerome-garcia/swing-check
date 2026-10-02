import numpy as np
import pytest

from swingcheck.body import body_scale, hands
from swingcheck.config import load_config
from swingcheck.models import LANDMARK_INDEX, LANDMARKS, PoseSeq

CFG = load_config()


def standing_pose(frames=60, fps=240.0, zoom=1.0, offset=(0.0, 0.0)):
    """Static pose: shoulders 120 px apart at y=400, hips at y=660 (torso 260 px)."""
    data = np.full((frames, len(LANDMARKS), 4), np.nan)
    pts = {
        "left_shoulder": (440, 400), "right_shoulder": (560, 400),
        "left_hip": (460, 660), "right_hip": (540, 660),
        "left_wrist": (495, 700), "right_wrist": (505, 700),
    }
    for name, (x, y) in pts.items():
        data[:, LANDMARK_INDEX[name]] = (x * zoom + offset[0], y * zoom + offset[1], 0.0, 0.95)
    return PoseSeq(fps=fps, width=1080, height=1920, data=data)


def test_torso_scale():
    assert body_scale(standing_pose(), 30, CFG) == pytest.approx(260)


def test_scale_follows_camera_distance_not_position():
    near = body_scale(standing_pose(zoom=1.5), 30, CFG)
    shifted = body_scale(standing_pose(offset=(100, -50)), 30, CFG)
    assert near == pytest.approx(390)
    assert shifted == pytest.approx(260)


def test_shoulder_width_method():
    cfg = {**CFG, "scale": {**CFG["scale"], "method": "shoulder_width"}}
    assert body_scale(standing_pose(), 30, cfg) == pytest.approx(120)


def test_one_bad_frame_does_not_skew_scale():
    pose = standing_pose()
    pose.data[30, LANDMARK_INDEX["left_hip"], 1] = 1200  # wild detection on the address frame itself
    cfg = {**CFG, "pose": {**CFG["pose"], "smoothing_ms": 0}}
    assert body_scale(pose, 30, cfg) == pytest.approx(260)


def test_hands_use_visible_wrist_when_other_hidden():
    pose = standing_pose()
    pose.data[:, LANDMARK_INDEX["left_wrist"], 3] = 0.05  # lead wrist hidden
    xy = hands(pose, CFG)
    assert xy[30] == pytest.approx([505, 700])
    pose.data[:, LANDMARK_INDEX["left_wrist"], 3] = 0.95
    assert hands(pose, CFG)[30] == pytest.approx([500, 700])
