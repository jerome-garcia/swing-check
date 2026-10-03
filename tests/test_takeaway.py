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


ADDR_CLUBHEAD = BALL + (-25, 10)
ADDR_GRIP = np.array([560.0, 820.0])


def on_line(inside_by):
    """A point partway up the address shaft line, moved inside_by body lengths square
    to it toward the golfer (screen-left here), for the right-handed scene."""
    d = (ADDR_GRIP - ADDR_CLUBHEAD) / np.linalg.norm(ADDR_GRIP - ADDR_CLUBHEAD)
    normal = np.array([-d[1], d[0]])
    if normal[0] > 0:
        normal = -normal
    return ADDR_CLUBHEAD + 0.6 * (ADDR_GRIP - ADDR_CLUBHEAD) + inside_by * SCALE * normal


def run(inside_by=None, mirror=False, config=None, hands=HANDS):
    """inside_by: the clubhead's distance from the address shaft line in body lengths
    (+ = golfer's side; None = takeaway not marked). mirror=True flips the whole scene
    for a left-hander."""
    config = copy.deepcopy(config or CONFIG)
    flip = (lambda p: (WIDTH - 1 - float(p[0]), float(p[1]))) if mirror else (lambda p: (float(p[0]), float(p[1])))
    if mirror:
        config["golfer"]["handedness"] = "left"
    checkpoints = {}
    if inside_by is not None:
        checkpoints["takeaway"] = CheckpointMark(frame=20, points={"clubhead": flip(on_line(inside_by)), "grip": flip(hands)})
    marks = Marks(view="dtl", address_frame=0,
                  points={"ball": flip(BALL), "clubhead": flip(ADDR_CLUBHEAD), "grip": flip(ADDR_GRIP)},
                  checkpoints=checkpoints)
    ctx = SwingContext(view="dtl", pose=pose(mirror), marks=marks, phases=PHASES, scale=SCALE, config=config)
    (v,) = [v for v in run_analyzers(ctx) if v.name == "takeaway"]
    return v


def test_clubhead_on_the_line_is_on_plane():
    v = run(inside_by=0.04)
    assert v.status == "ok" and v.label == "Club on plane"
    assert v.phase == "takeaway"


def test_clubhead_behind_the_line_is_inside():
    v = run(inside_by=0.3)
    assert v.status == "flag" and v.label == "Clubhead inside the line"
    assert v.measurements["clubhead_inside_line"] == pytest.approx(0.3, abs=1e-3)
    assert v.rows[0].value == "0.30 inside"


def test_clubhead_in_front_of_the_line_is_outside():
    v = run(inside_by=-0.2)
    assert v.status == "flag" and v.label == "Clubhead outside the line"
    assert v.measurements["clubhead_inside_line"] == pytest.approx(-0.2, abs=1e-3)


def test_hands_position_doesnt_matter():
    # Clubhead right over the hands but well inside the line: still inside.
    assert run(inside_by=0.3, hands=on_line(0.3)).label == "Clubhead inside the line"


def test_tolerance_from_config():
    config = copy.deepcopy(CONFIG)
    config["analyzers"]["takeaway"]["line_tolerance"] = 0.03
    assert run(inside_by=0.04, config=config).status == "flag"


def test_left_handed_mirror_matches():
    for x in (0.3, 0.04, -0.2):
        right, left = run(inside_by=x), run(inside_by=x, mirror=True)
        assert left.label == right.label
        assert left.measurements["clubhead_inside_line"] == pytest.approx(
            right.measurements["clubhead_inside_line"], abs=1e-3)


def test_not_marked_explains_how():
    v = run(inside_by=None)
    assert v.status == "error"
    assert "Takeaway" in v.summary
