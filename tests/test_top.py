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


def pose(mirror=False, head=None, heel_x=None, upright=0.0):
    """heel_x: screen x of the trail (right) heel; None = heel not tracked. upright: px the
    shoulders sit back toward the golfer's back at the top (spine bend lost)."""
    head = HEAD if head is None else head
    data = np.full((60, len(LANDMARKS), 4), np.nan)
    for f in range(60):
        pts = {"left_hip": HIP + (40, 0), "right_hip": HIP - (40, 0),
               "left_ear": head + (6, 0), "right_ear": head - (6, 0),
               "left_shoulder": LEAD_SHOULDER_TOP - (upright, 0) if f >= 20 else SHOULDER_MID + (60, 40),
               "right_shoulder": 2 * SHOULDER_MID - LEAD_SHOULDER_TOP - (upright, 0) if f >= 20 else TRAIL_SHOULDER_ADDR}
        if heel_x is not None:
            pts["right_heel"] = np.array([heel_x, 1600.0])
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


def run(hands, mirror=False, config=None, marked=True, head=None, heel_out=0.0, heel=True, upright=0.0):
    """heel_out: torso lengths the hands sit out toward the ball from the trail heel."""
    config = copy.deepcopy(config or CONFIG)
    flip = (lambda p: (WIDTH - 1 - float(p[0]), float(p[1]))) if mirror else (lambda p: (float(p[0]), float(p[1])))
    if mirror:
        config["golfer"]["handedness"] = "left"
    checkpoints = {"top": CheckpointMark(frame=30, points={"clubhead": flip(hands + (-60, -80)), "grip": flip(hands)})} \
        if marked else {}
    marks = Marks(view="dtl", address_frame=0,
                  points={"ball": flip(BALL), "clubhead": flip(ADDR_CLUBHEAD), "grip": flip(ADDR_GRIP)},
                  checkpoints=checkpoints)
    ctx = SwingContext(view="dtl", pose=pose(mirror, head, hands[0] - heel_out * SCALE if heel else None, upright), marks=marks, phases=PHASES, scale=SCALE, config=config)
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
    (90, "ok", "Front arm matches your shoulders"),
    (70, "warn", "Front arm slightly above your shoulders"),
    (60, "flag", "Front arm above your shoulders"),
    (110, "warn", "Front arm slightly below your shoulders"),
    (120, "flag", "Front arm below your shoulders"),
])
def test_arm_bands(arm, status, label):
    v = run(hands_at(arm))
    assert v.measurements["arm_to_spine_deg"] == pytest.approx(arm, abs=0.1)
    assert v.rows[0].status == status and label.lower() in v.label.lower()
    assert v.frame == 30


def test_left_handed_mirror_matches():
    for h in (hands_at(90), hands_at(60), hands_at(120)):
        right, left = run(h), run(h, mirror=True)
        assert left.label == right.label
        assert left.measurements["arm_to_spine_deg"] == pytest.approx(right.measurements["arm_to_spine_deg"], abs=0.1)


def test_not_marked_explains_how():
    v = run(hands_at(90), marked=False)
    assert v.status == "error" and "Top" in v.summary


def test_judges_the_arm_and_the_hands_over_the_heel():
    v = run(hands_at(90))
    assert [r.label for r in v.rows] == ["Front arm vs spine", "Hands vs back heel", "Spine bend kept"]
    assert v.label == "Front arm matches your shoulders" and v.tip == ""
    assert v.measurements["hands_out_from_heel"] == pytest.approx(0.0, abs=1e-3)


@pytest.mark.parametrize("out, status, label", [
    (0.03, "ok", "Hands over your back heel"),      # McIlroy
    (-0.12, "ok", "Hands over your back heel"),
    (0.2, "warn", "Hands slightly toward the ball"),
    (0.4, "warn", "Hands too far toward the ball"),  # past the red line, but Watch at most
    (-0.2, "warn", "Hands slightly behind your back heel"),
    (-0.4, "warn", "Hands behind your back heel"),
])
def test_hands_vs_trail_heel_bands(out, status, label):
    for mirror in (False, True):
        v = run(hands_at(90), heel_out=out, mirror=mirror)
        row = v.rows[1]
        assert row.status == status and row.note == label.removeprefix("Hands ").capitalize()
        assert v.status == status  # the arm is green, so the hands decide
        assert v.measurements["hands_out_from_heel"] == pytest.approx(out, abs=1e-3)
        assert row.value.endswith("toward the ball" if out >= 0 else "behind")
        assert (row.good, row.fix) == ("within 8 cm of your heel", "")  # never Fix: no red range
        assert (label.lower() in v.label.lower()) == (status != "ok")
        assert (v.tip == "") == (status == "ok")


def test_heel_not_tracked_is_not_measured():
    v = run(hands_at(90), heel=False)
    assert v.rows[1].status == "error" and v.rows[1].value == "Not measured"
    assert v.status == "ok" and v.measurements["hands_out_from_heel"] is None


def test_key_frame_shows_the_trail_heel_line():
    assert any(o.kind == "dashed" and o.label == "Back heel" for o in run(hands_at(90)).overlays)


def test_key_frame_shows_the_swing_plane_line():
    assert any(o.kind == "line" and o.label == "Swing plane" for o in run(hands_at(90)).overlays)



@pytest.mark.parametrize("upright, status, extra", [
    (0, "ok", None),                         # spine bend held (McIlroy)
    (60, "warn", "slightly standing up"),    # about 11° more upright
    (80, "flag", "standing up"),             # about 15° (jolo loses 13°)
])
def test_spine_bend_kept_at_the_top(upright, status, extra):
    for mirror in (False, True):
        v = run(hands_at(90), upright=upright, mirror=mirror)
        row = v.rows[2]
        assert row.label == "Spine bend kept" and row.status == status
        assert row.good == "up to 8° more upright or 5° more bent"
        assert v.status == status
        assert v.label == "Front arm matches your shoulders" + (f", {extra}" if extra else "")
        assert v.rows[0].note == "Matches your shoulders"  # the arm row's own wording
        # The posture lines are drawn only when it's off (the top already has a spine line).
        assert any(o.label == "Address spine" for o in v.overlays) == (status != "ok")
