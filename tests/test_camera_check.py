"""Camera check: a clean down-the-line view passes; the usual filming mistakes are named."""

import cv2
import numpy as np

from swingcheck.camera_check import camera_check, facing, facing_finding, motion_finding, motion_from_frames
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


def test_facing_depends_on_handedness():
    mirrored = {k: (W - x, y) for k, (x, y) in DTL.items()}  # a left-hander, filmed from behind
    assert titles(mirrored) == []  # the camera itself is fine
    assert facing(pose_of(DTL), 5) == 1 and facing(pose_of(mirrored), 5) == -1
    assert facing_finding(-1, "right")["title"] == "You're facing left"
    assert "switch this swing to left-handed" in facing_finding(-1, "right")["tip"]
    assert facing_finding(-1, "left") is None and facing_finding(1, "right") is None
    assert facing_finding(1, "left")["title"] == "You're facing right"
    assert facing_finding(None, "right") is None  # no golfer found


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


def test_face_on_wants_the_body_wide():
    def fo_titles(points):
        return [f["title"] for f in camera_check(pose_of(points), 5, load_config(), view="fo")]

    assert fo_titles(spread_by(110)) == []                                                # ~0.75 torso: face-on
    assert fo_titles(spread_by(50)) == ["The camera may be at an angle"]                 # ~0.34
    assert fo_titles(DTL) == ["This doesn't look like a face-on view"]                   # from behind
    assert camera_check(pose_of(DTL), 5, load_config(), view=None) == []                 # angle left for later


def test_body_spread_is_saved_for_either_view():
    from swingcheck.camera_check import body_spread
    assert 0.7 < body_spread(pose_of(spread_by(110)), 5) < 0.8
    assert body_spread(pose_of(DTL), 5) < 0.1


def textured(shift_x=0, blob_x=None, seed=1):
    """A 240x320 frame of fixed random texture, slid shift_x px sideways (a panning camera),
    with an optional bright moving blob in the middle (the golfer and club)."""
    rng = np.random.default_rng(seed)
    big = cv2.GaussianBlur(rng.random((240, 480)).astype(np.float32), (0, 0), 2)
    frame = big[:, 80 + shift_x:400 + shift_x].copy()
    if blob_x is not None:
        frame[60:220, blob_x:blob_x + 60] = 1.0
    return frame


def test_a_still_camera_with_a_moving_golfer_isnt_counted_as_moving():
    frames = [textured(blob_x=x) for x in (130, 120, 140, 110, 150, 130)]
    assert motion_from_frames(frames) < 0.02


def test_a_panning_camera_is_caught():
    frames = [textured(shift_x=s, blob_x=130) for s in (0, 10, 25, 45, 60, 60)]
    moved = motion_from_frames(frames)
    assert moved >= 0.12
    assert [f["title"] for f in motion_finding(moved, load_config())] == ["The camera moved during the clip"]


def test_a_one_frame_jump_doesnt_count():
    frames = [textured(), textured(), textured(shift_x=60), textured(), textured()]  # e.g. a dropped frame
    assert motion_from_frames(frames) < 0.02


def test_motion_finding_levels():
    cfg = load_config()
    assert motion_finding(0.04, cfg) == []
    assert motion_finding(0.08, cfg)[0]["level"] == "warn"
    assert motion_finding(0.20, cfg)[0]["level"] == "flag"
