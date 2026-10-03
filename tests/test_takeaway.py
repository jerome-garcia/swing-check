import copy

import numpy as np
import pytest

from swingcheck.analyzers import SwingContext, run_analyzers
from swingcheck.config import load_config
from swingcheck.models import CheckpointMark, LANDMARK_INDEX, LANDMARKS, Marks, PoseSeq
from swingcheck.phases import Phases

CONFIG = load_config()
SCALE = 260.0
WIDTH = 1080
PHASES = Phases(address=0, takeaway=20, top=40, early_downswing=50, impact=60)
HIP = np.array([300.0, 700.0])  # golfer on the left, ball on the right (right-hander, DTL)
BALL = np.array([800.0, 1150.0])
HANDS = np.array([520.0, 760.0])


def pose(mirror=False):
    data = np.full((80, len(LANDMARKS), 4), np.nan)
    for name, p in {"left_hip": HIP, "right_hip": HIP, "left_shoulder": HIP + (150, -210),
                    "right_shoulder": HIP + (150, -210)}.items():
        x = WIDTH - 1 - p[0] if mirror else p[0]
        data[:, LANDMARK_INDEX[name]] = (x, p[1], 0.0, 0.95)
    return PoseSeq(fps=240.0, width=WIDTH, height=1920, data=data)


def run(clubhead_dx=None, mirror=False, config=None):
    """clubhead_dx: the clubhead's screen-x offset from the hands in px, for the right-handed
    scene (None = takeaway not marked). mirror=True flips the whole scene for a left-hander."""
    config = copy.deepcopy(config or CONFIG)
    flip = (lambda p: (WIDTH - 1 - float(p[0]), float(p[1]))) if mirror else (lambda p: (float(p[0]), float(p[1])))
    if mirror:
        config["golfer"]["handedness"] = "left"
    checkpoints = {}
    if clubhead_dx is not None:
        clubhead = HANDS + (clubhead_dx, 25)
        checkpoints["takeaway"] = CheckpointMark(frame=20, points={"clubhead": flip(clubhead), "grip": flip(HANDS)})
    marks = Marks(view="dtl", address_frame=0,
                  points={"ball": flip(BALL), "clubhead": flip(BALL + (-25, 10)), "grip": flip((560, 820))},
                  checkpoints=checkpoints)
    ctx = SwingContext(view="dtl", pose=pose(mirror), marks=marks, phases=PHASES, scale=SCALE, config=config)
    (v,) = [v for v in run_analyzers(ctx) if v.name == "takeaway"]
    return v


def test_clubhead_in_front_of_hands_covers():
    v = run(clubhead_dx=10)  # 0.04 body lengths toward the ball
    assert v.status == "ok" and v.label == "Club covers the hands"
    assert v.phase == "takeaway"


def test_clubhead_toward_golfer_is_inside():
    v = run(clubhead_dx=-0.2 * SCALE)  # golfer is screen-left
    assert v.status == "flag" and v.label == "Clubhead inside the hands"
    assert v.measurements["clubhead_inside_hands"] == pytest.approx(0.2, abs=1e-3)
    assert v.rows[0].value == "0.20 inside"


def test_clubhead_toward_ball_is_outside():
    v = run(clubhead_dx=0.2 * SCALE)
    assert v.status == "flag" and v.label == "Clubhead outside the hands"
    assert v.measurements["clubhead_inside_hands"] == pytest.approx(-0.2, abs=1e-3)


def test_tolerance_from_config():
    config = copy.deepcopy(CONFIG)
    config["analyzers"]["takeaway"]["covering_tolerance"] = 0.03
    assert run(clubhead_dx=10, config=config).status == "flag"


def test_left_handed_mirror_matches():
    for dx in (-0.2 * SCALE, 10, 0.2 * SCALE):
        right, left = run(clubhead_dx=dx), run(clubhead_dx=dx, mirror=True)
        assert left.label == right.label
        assert left.measurements["clubhead_inside_hands"] == pytest.approx(
            right.measurements["clubhead_inside_hands"], abs=1e-3)


def test_not_marked_explains_how():
    v = run(clubhead_dx=None)
    assert v.status == "error"
    assert "Takeaway" in v.summary
