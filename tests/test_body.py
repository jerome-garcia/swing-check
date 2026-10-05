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


def test_hands_average_wrists_that_agree():
    pose = standing_pose()
    assert hands(pose, CFG)[30] == pytest.approx([500, 700])
    pose.data[:, LANDMARK_INDEX["left_wrist"], 3] = 0.05  # low visibility but agreeing: still averaged
    assert hands(pose, CFG)[30] == pytest.approx([500, 700])


def test_lone_low_visibility_wrist_ignored():
    pose = standing_pose(frames=60)
    pose.data[:, LANDMARK_INDEX["right_wrist"]] = np.nan
    pose.data[:, LANDMARK_INDEX["left_wrist"], 3] = 0.05
    assert np.isnan(hands(pose, CFG)).all()


def test_hands_follow_the_wrist_that_continues_the_path():
    # Hands rise steadily; from frame 30 the *visible* trail wrist drifts toward
    # the body while the low-visibility lead wrist keeps following the real path.
    pose = standing_pose(frames=60)
    t = np.arange(60, dtype=float)
    true_x, true_y = 500 - 2 * t, 700 - 4 * t
    lw, rw = LANDMARK_INDEX["left_wrist"], LANDMARK_INDEX["right_wrist"]
    pose.data[:, lw, 0], pose.data[:, lw, 1] = true_x, true_y
    pose.data[:, rw, 0], pose.data[:, rw, 1] = true_x, true_y
    drift = np.clip(t - 30, 0, None) * 12
    pose.data[:, rw, 0] += drift
    pose.data[30:, lw, 3] = 0.1   # "hidden"
    pose.data[30:, rw, 3] = 0.9   # "visible" but wrong
    cfg = {**CFG, "pose": {**CFG["pose"], "smoothing_ms": 0}}
    xy = hands(pose, cfg)
    assert np.abs(xy[45:, 0] - true_x[45:]).max() < 3


def test_lone_wrist_glitch_is_interpolated_over():
    pose = standing_pose(frames=60)
    lw, rw = LANDMARK_INDEX["left_wrist"], LANDMARK_INDEX["right_wrist"]
    pose.data[:, lw] = np.nan                      # only one wrist tracked
    pose.data[25, rw, 0] += 200                    # one-frame glitch, ~0.8 torso
    cfg = {**CFG, "pose": {**CFG["pose"], "smoothing_ms": 0}}
    xy = hands(pose, cfg)
    assert xy[25] == pytest.approx([505, 700])


def test_list_text_uses_the_oxford_comma():
    from swingcheck.analyzers.dtl_body import list_text
    assert list_text(["arms reach"]) == "arms reach"
    assert list_text(["arms reach", "knees lock"]) == "arms reach and knees lock"
    assert list_text(["a", "b", "c"]) == "a, b, and c"
