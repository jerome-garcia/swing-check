import copy

import numpy as np
import pytest

from swingcheck.analyzers import SwingContext, run_analyzers
from swingcheck.config import load_config
from swingcheck.models import CheckpointMark, LANDMARK_INDEX, LANDMARKS, Marks, PoseSeq
from swingcheck.phases import Phases

CONFIG = load_config()
SCALE = 300.0
WIDTH = 1080
PHASES = Phases(address=0, takeaway=20, top=40, early_downswing=50, impact=60)
# Right-hander from behind: golfer on the left, ball on the right (the reference photo, roughly).
HIP = np.array([360.0, 1070.0])
BALL = np.array([806.0, 1484.0])
TRAIL_SHOULDER = np.array([464.0, 775.0])
TRAIL_ELBOW = np.array([486.0, 906.0])
HANDS = np.array([450.0, 865.0])


def pose(mirror=False):
    data = np.full((80, len(LANDMARKS), 4), np.nan)
    pts = {"left_hip": HIP + (45, 5), "right_hip": HIP - (45, 5), "left_shoulder": (585.0, 850.0),
           "right_shoulder": TRAIL_SHOULDER, "right_elbow": TRAIL_ELBOW}
    for name, p in pts.items():
        if mirror:  # a left-hander is the mirror image, with left and right swapped
            name = name.replace("left", "tmp").replace("right", "left").replace("tmp", "right")
            p = (WIDTH - 1 - p[0], p[1])
        data[:, LANDMARK_INDEX[name]] = (p[0], p[1], 0.0, 0.95)
    return PoseSeq(fps=240.0, width=WIDTH, height=1920, data=data)


def clubhead_for(inside_by, hands=HANDS):
    """A clubhead up and behind the hands so the shaft lands inside_by torso lengths inside the ball."""
    landing = np.array([BALL[0] - inside_by * SCALE, BALL[1]])
    return hands + (hands - landing) * 0.9


def run(inside_by=0.25, hands=HANDS, mirror=False, config=None, marked=True, clubhead=None):
    config = copy.deepcopy(config or CONFIG)
    flip = (lambda p: (WIDTH - 1 - float(p[0]), float(p[1]))) if mirror else (lambda p: (float(p[0]), float(p[1])))
    if mirror:
        config["golfer"]["handedness"] = "left"
    checkpoints = {}
    if marked:
        ch = clubhead if clubhead is not None else clubhead_for(inside_by, hands)
        checkpoints["halfway_back"] = CheckpointMark(frame=30, points={"clubhead": flip(ch), "grip": flip(hands)})
    marks = Marks(view="dtl", address_frame=0,
                  points={"ball": flip(BALL), "clubhead": flip(BALL + (-25, 10)), "grip": flip((560, 820))},
                  checkpoints=checkpoints)
    ctx = SwingContext(view="dtl", pose=pose(mirror), marks=marks, phases=PHASES, scale=SCALE, config=config)
    (v,) = [v for v in run_analyzers(ctx) if v.name == "halfway_back"]
    return v


def test_reference_photo_is_green():
    v = run(clubhead=np.array([183.0, 268.0]))  # the photo's clubhead and hands
    assert v.status == "ok"
    assert v.label == "Points just inside the ball, hands split the biceps"
    assert v.measurements["shaft_inside_ball"] == pytest.approx(0.26, abs=0.01)
    assert v.measurements["hands_out_from_biceps"] == pytest.approx(-0.10, abs=0.01)
    assert v.frame == 30  # key frame is the marked frame


@pytest.mark.parametrize("inside_by, status, label", [
    (0.2, "ok", "Points just inside the ball"),
    (0.55, "warn", "Points well inside the ball"),
    (0.9, "flag", "Points at your feet"),
    (-0.1, "warn", "Points just outside the ball"),
    (-0.3, "flag", "Points outside the ball"),
])
def test_shaft_bands(inside_by, status, label):
    v = run(inside_by=inside_by)
    row = v.rows[0]
    assert row.status == status and label.lower() in row.note
    assert v.measurements["shaft_inside_ball"] == pytest.approx(inside_by, abs=1e-3)


@pytest.mark.parametrize("dx, status, label", [
    (0.0, "ok", "Hands split the biceps"),
    (0.2, "warn", "Hands slightly in front of the arm"),
    (-0.2, "warn", "Hands slightly behind the arm"),
    (0.4, "flag", "Hands far out in front of the arm"),
    (-0.4, "flag", "Hands deep behind the arm"),
])
def test_hands_bands(dx, status, label):
    # Hands moved sideways (toward the ball = screen right here) from the biceps line.
    arm_x = TRAIL_SHOULDER[0] + (HANDS[1] - TRAIL_SHOULDER[1]) * (TRAIL_ELBOW[0] - TRAIL_SHOULDER[0]) / (TRAIL_ELBOW[1] - TRAIL_SHOULDER[1])
    hands = np.array([arm_x + dx * SCALE, HANDS[1]])
    v = run(hands=hands)
    row = v.rows[1]
    assert row.status == status and label.lower() in row.note
    assert v.measurements["hands_out_from_biceps"] == pytest.approx(dx, abs=1e-3)


def test_worst_color_wins_and_rows_have_units():
    v = run(inside_by=0.9)
    assert v.status == "flag"
    assert v.rows[0].value == "≈45 cm inside the ball"  # 90% of the default 50 cm torso
    assert "of torso length" in v.rows[0].note and "green 0%–40% inside" in v.rows[0].note


def test_left_handed_mirror_matches():
    for x in (0.2, 0.55, -0.3):
        right, left = run(inside_by=x), run(inside_by=x, mirror=True)
        assert left.label == right.label
        for key in ("shaft_inside_ball", "hands_out_from_biceps"):
            assert left.measurements[key] == pytest.approx(right.measurements[key], abs=1e-3)


def test_bands_from_config():
    config = copy.deepcopy(CONFIG)
    config["analyzers"]["halfway_back"]["inside_max"] = 0.1
    assert run(inside_by=0.2, config=config).rows[0].status == "warn"


def test_not_marked_explains_how():
    v = run(marked=False)
    assert v.status == "error" and "Halfway back" in v.summary


def test_clubhead_below_hands_is_a_marking_error():
    v = run(clubhead=HANDS + (50, 100))
    assert v.status == "error" and "above the hands" in v.summary


def test_frame_too_early_says_so():
    # Hands well below the trail elbow: before lead arm parallel.
    v = run(hands=TRAIL_ELBOW + (-10, 0.3 * SCALE))
    assert v.status == "error" and "later frame" in v.summary
