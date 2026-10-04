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
HANDS = np.array([450.0, 865.0])


def pose(mirror=False):
    data = np.full((80, len(LANDMARKS), 4), np.nan)
    for name, p in {"left_hip": HIP + (45, 5), "right_hip": HIP - (45, 5)}.items():
        x = WIDTH - 1 - p[0] if mirror else p[0]
        data[:, LANDMARK_INDEX[name]] = (x, p[1], 0.0, 0.95)
    return PoseSeq(fps=240.0, width=WIDTH, height=1920, data=data)


def clubhead_for(inside_by, hands=HANDS):
    """A clubhead up and behind the hands so the shaft lands inside_by torso lengths inside the ball."""
    landing = np.array([BALL[0] - inside_by * SCALE, BALL[1]])
    return hands + (hands - landing) * 0.9


def run(inside_by=0.25, mirror=False, config=None, marked=True, clubhead=None):
    config = copy.deepcopy(config or CONFIG)
    flip = (lambda p: (WIDTH - 1 - float(p[0]), float(p[1]))) if mirror else (lambda p: (float(p[0]), float(p[1])))
    if mirror:
        config["golfer"]["handedness"] = "left"
    checkpoints = {}
    if marked:
        ch = clubhead if clubhead is not None else clubhead_for(inside_by)
        checkpoints["halfway_back"] = CheckpointMark(frame=30, points={"clubhead": flip(ch), "grip": flip(HANDS)})
    marks = Marks(view="dtl", address_frame=0,
                  points={"ball": flip(BALL), "clubhead": flip(BALL + (-25, 10)), "grip": flip((560, 820))},
                  checkpoints=checkpoints)
    ctx = SwingContext(view="dtl", pose=pose(mirror), marks=marks, phases=PHASES, scale=SCALE, config=config)
    (v,) = [v for v in run_analyzers(ctx) if v.name == "halfway_back"]
    return v


def test_reference_photo_is_green():
    v = run(clubhead=np.array([183.0, 268.0]))  # the photo's clubhead and hands
    assert v.status == "ok" and v.label == "Points just inside the ball"
    assert v.measurements["shaft_inside_ball"] == pytest.approx(0.26, abs=0.01)
    assert v.frame == 30  # key frame is the marked frame
    assert [r.label for r in v.rows] == ["Shaft points", "Halfway frame"]  # no biceps check


@pytest.mark.parametrize("inside_by, status, label", [
    (0.2, "ok", "Points just inside the ball"),
    (-0.05, "ok", "Points at the ball"),
    (0.55, "warn", "Points well inside the ball"),
    (0.9, "flag", "Points at your feet"),
    (-0.15, "warn", "Points just outside the ball"),
    (-0.4, "flag", "Points outside the ball"),
])
def test_shaft_bands(inside_by, status, label):
    v = run(inside_by=inside_by)
    assert v.status == status and v.label == label
    assert v.measurements["shaft_inside_ball"] == pytest.approx(inside_by, abs=1e-3)
    assert (v.tip == "") == (status == "ok")


def test_row_has_units_and_limits():
    row = run(inside_by=0.9).rows[0]
    assert row.value == "≈45 cm inside the ball"  # 90% of the default 50 cm torso
    assert "of torso length" in row.note and "green 10% outside to 40% inside" in row.note


def test_left_handed_mirror_matches():
    for x in (0.2, 0.55, -0.4):
        right, left = run(inside_by=x), run(inside_by=x, mirror=True)
        assert left.label == right.label
        assert left.measurements["shaft_inside_ball"] == pytest.approx(right.measurements["shaft_inside_ball"], abs=1e-3)


def test_bands_from_config():
    config = copy.deepcopy(CONFIG)
    config["analyzers"]["halfway_back"]["inside_max"] = 0.1
    assert run(inside_by=0.2, config=config).status == "warn"


def test_not_marked_explains_how():
    v = run(marked=False)
    assert v.status == "error" and "Halfway back" in v.summary


def test_clubhead_below_hands_is_a_marking_error():
    v = run(clubhead=HANDS + (50, 100))
    assert v.status == "error" and "above the hands" in v.summary


def test_key_frame_shows_the_swing_plane_line():
    assert any(o.kind == "line" and o.label == "swing plane" for o in run().overlays)
