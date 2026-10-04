import copy

import numpy as np
import pytest

from swingcheck.analyzers import SwingContext, run_analyzers
from swingcheck.config import load_config
from swingcheck.geometry import angle_between_deg
from swingcheck.models import CheckpointMark, LANDMARK_INDEX, LANDMARKS, Marks, PoseSeq
from swingcheck.phases import Phases

CONFIG = load_config()
SCALE = 300.0
WIDTH = 1080
PHASES = Phases(address=0, takeaway=10, top=30, early_downswing=40, impact=50)
# Right-hander from behind: golfer on the left, ball on the right.
BALL = np.array([800.0, 1480.0])
ADDR_CLUBHEAD, ADDR_GRIP = BALL + (-20, 5), np.array([520.0, 1080.0])  # address shaft line
HIP = np.array([360.0, 1070.0])
SHOULDER_MID = np.array([530.0, 840.0])  # spine leans toward the ball
TRAIL_SHOULDER_ADDR = np.array([480.0, 800.0])
LEAD_SHOULDER_TOP = np.array([590.0, 880.0])
HEAD = HIP + 1.3 * (SHOULDER_MID - HIP)  # the spine runs from the hips through the head


def pose(mirror=False, head=None):
    head = HEAD if head is None else head
    data = np.full((60, len(LANDMARKS), 4), np.nan)
    for f in range(60):
        pts = {"left_hip": HIP + (40, 0), "right_hip": HIP - (40, 0),
               "left_ear": head + (6, 0), "right_ear": head - (6, 0),
               "left_shoulder": LEAD_SHOULDER_TOP if f >= 20 else SHOULDER_MID + (60, 40),
               "right_shoulder": 2 * SHOULDER_MID - LEAD_SHOULDER_TOP if f >= 20 else TRAIL_SHOULDER_ADDR}
        for name, p in pts.items():
            if mirror:
                name = name.replace("left", "tmp").replace("right", "left").replace("tmp", "right")
                p = (WIDTH - 1 - p[0], p[1])
            data[f, LANDMARK_INDEX[name]] = (p[0], p[1], 0.0, 0.95)
    return PoseSeq(fps=240.0, width=WIDTH, height=1920, data=data)


def hands_at(arm_deg, length=300.0):
    """Hands placed so the lead arm (lead shoulder -> hands) makes arm_deg with the spine."""
    spine = (SHOULDER_MID - HIP) / np.linalg.norm(SHOULDER_MID - HIP)
    a = np.radians(arm_deg)
    # Rotate the spine direction toward the golfer's back (screen left here).
    rot = np.array([[np.cos(a), np.sin(a)], [-np.sin(a), np.cos(a)]])
    return LEAD_SHOULDER_TOP + length * (rot @ spine)


def run(hands, mirror=False, config=None, marked=True, head=None):
    config = copy.deepcopy(config or CONFIG)
    flip = (lambda p: (WIDTH - 1 - float(p[0]), float(p[1]))) if mirror else (lambda p: (float(p[0]), float(p[1])))
    if mirror:
        config["golfer"]["handedness"] = "left"
    checkpoints = {"top": CheckpointMark(frame=30, points={"clubhead": flip(hands + (-60, -80)), "grip": flip(hands)})} \
        if marked else {}
    marks = Marks(view="dtl", address_frame=0,
                  points={"ball": flip(BALL), "clubhead": flip(ADDR_CLUBHEAD), "grip": flip(ADDR_GRIP)},
                  checkpoints=checkpoints)
    ctx = SwingContext(view="dtl", pose=pose(mirror, head), marks=marks, phases=PHASES, scale=SCALE, config=config)
    (v,) = [v for v in run_analyzers(ctx) if v.name == "top"]
    return v


def test_helper_places_the_arm_angle():
    h = hands_at(90)
    assert angle_between_deg(h - LEAD_SHOULDER_TOP, SHOULDER_MID - HIP) == pytest.approx(90)


def test_spine_runs_through_the_head_not_the_shoulders():
    # Same arm; tilt the head line 10 degrees further forward: the arm-to-spine angle follows the head.
    h = hands_at(90)
    base = run(h).measurements["arm_to_spine_deg"]
    a = np.radians(10)
    rot = np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]])
    tilted = HIP + rot @ (HEAD - HIP)
    assert abs(run(h, head=tilted).measurements["arm_to_spine_deg"] - base) == pytest.approx(10, abs=0.2)


@pytest.mark.parametrize("arm, status, label", [
    (90, "ok", "Lead arm matches the shoulders"),
    (70, "warn", "Lead arm slightly above the shoulders"),
    (60, "flag", "Lead arm above the shoulders"),
    (110, "warn", "Lead arm slightly below the shoulders"),
    (120, "flag", "Lead arm below the shoulders"),
])
def test_arm_bands(arm, status, label):
    v = run(hands_at(arm))
    assert v.measurements["arm_to_spine_deg"] == pytest.approx(arm, abs=0.1)
    assert v.rows[0].status == status and label.lower() in v.rows[0].note
    assert v.frame == 30


def test_left_handed_mirror_matches():
    for h in (hands_at(90), hands_at(60), hands_at(120)):
        right, left = run(h), run(h, mirror=True)
        assert left.label == right.label
        assert left.measurements["arm_to_spine_deg"] == pytest.approx(right.measurements["arm_to_spine_deg"], abs=0.1)


def test_not_marked_explains_how():
    v = run(hands_at(90), marked=False)
    assert v.status == "error" and "Top" in v.summary


def test_judges_the_arm_only():
    v = run(hands_at(90))
    assert [r.label for r in v.rows] == ["Lead arm vs spine", "Top frame"]
    assert v.label == "Lead arm matches the shoulders" and v.tip == ""


def test_key_frame_shows_the_swing_plane_line():
    assert any(o.kind == "line" and o.label == "swing plane" for o in run(hands_at(90)).overlays)
