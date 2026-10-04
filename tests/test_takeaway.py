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


@pytest.mark.parametrize("inside_by, status, label", [
    (0.15, "ok", "Club on plane"),
    (0.3, "warn", "Clubhead slightly inside the swing plane"),
    (-0.45, "warn", "Clubhead slightly outside the swing plane"),
    (0.6, "flag", "Clubhead well inside the swing plane"),
    (-0.6, "flag", "Clubhead well outside the swing plane"),
])
def test_inside_and_outside_tiers(inside_by, status, label):
    v = run(inside_by=inside_by)
    assert v.status == status and v.label == label
    assert v.measurements["clubhead_inside_line"] == pytest.approx(inside_by, abs=1e-3)


def test_row_shows_offset_with_units():
    row = run(inside_by=0.3).rows[0]
    assert row.value == "≈15 cm inside"  # 30% of the default 50 cm torso
    assert row.note == "30% of torso length · slightly inside the swing plane (green within ±20%, red past 50%)"
    assert run(inside_by=-0.6).rows[0].value == "≈30 cm outside"


def test_hands_position_doesnt_matter():
    # Clubhead right over the hands but well inside the line: still inside.
    assert run(inside_by=0.6, hands=on_line(0.6)).label == "Clubhead well inside the swing plane"


def test_tolerance_from_config():
    config = copy.deepcopy(CONFIG)
    config["analyzers"]["takeaway"]["line_tolerance"] = 0.03
    config["analyzers"]["takeaway"]["flag_distance"] = 0.2
    assert run(inside_by=0.04, config=config).status == "warn"
    assert run(inside_by=0.3, config=config).status == "flag"
    config["golfer"]["torso_cm"] = 60
    assert run(inside_by=0.3, config=config).rows[0].value == "≈18 cm inside"


def test_left_handed_mirror_matches():
    for x in (0.6, 0.3, 0.04, -0.3, -0.6):
        right, left = run(inside_by=x), run(inside_by=x, mirror=True)
        assert left.label == right.label
        assert left.measurements["clubhead_inside_line"] == pytest.approx(
            right.measurements["clubhead_inside_line"], abs=1e-3)


def test_not_marked_explains_how():
    v = run(inside_by=None)
    assert v.status == "error"
    assert "Takeaway" in v.summary


def test_tip_only_when_off():
    assert run(inside_by=0.04).tip == ""
    assert "outside your hands" in run(inside_by=0.6).tip
    assert "turning your chest" in run(inside_by=-0.6).tip
