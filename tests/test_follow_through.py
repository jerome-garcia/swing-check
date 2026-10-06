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
PHASES = Phases(address=0, takeaway=10, top=20, early_downswing=30, impact=40)
HIP = np.array([360.0, 1070.0])  # golfer on the left, ball on the right (right-hander, DTL)
BALL = np.array([806.0, 1484.0])
HANDS = np.array([380.0, 700.0])


def pose(mirror=False):
    data = np.full((80, len(LANDMARKS), 4), np.nan)
    for name, p in {"left_hip": HIP + (45, 5), "right_hip": HIP - (45, 5)}.items():
        x = WIDTH - 1 - p[0] if mirror else p[0]
        data[:, LANDMARK_INDEX[name]] = (x, p[1], 0.0, 0.95)
    return PoseSeq(fps=240.0, width=WIDTH, height=1920, data=data)


def clubhead_for(inside_by, hands=HANDS):
    """A clubhead up and behind the hands so the shaft lands inside_by torso lengths inside the ball."""
    landing = np.array([BALL[0] - inside_by * SCALE, BALL[1]])
    return hands + (hands - landing) * 0.6


def run(inside_by=0.1, back=0.2, mirror=False, config=None, marked=True):
    config = copy.deepcopy(config or CONFIG)
    flip = (lambda p: (WIDTH - 1 - float(p[0]), float(p[1]))) if mirror else (lambda p: (float(p[0]), float(p[1])))
    if mirror:
        config["golfer"]["handedness"] = "left"
    checkpoints = {}
    if back is not None:
        hb_hands = np.array([450.0, 865.0])
        checkpoints["halfway_back"] = CheckpointMark(frame=15, points={"clubhead": flip(clubhead_for(back, hb_hands)),
                                                                       "grip": flip(hb_hands)})
    if marked:
        checkpoints["follow_through"] = CheckpointMark(frame=50, points={"clubhead": flip(clubhead_for(inside_by)),
                                                                         "grip": flip(HANDS)})
    marks = Marks(view="dtl", address_frame=0,
                  points={"ball": flip(BALL), "clubhead": flip(BALL + (-25, 10)), "grip": flip((560, 1100))},
                  checkpoints=checkpoints)
    ctx = SwingContext(view="dtl", pose=pose(mirror), marks=marks, phases=PHASES, scale=SCALE, config=config)
    (v,) = [v for v in run_analyzers(ctx) if v.name == "follow_through"]
    return v


def test_reference_like_exit_is_green():
    v = run(inside_by=0.02, back=0.2)  # the reference photos: on the ball, 20% inside going back
    assert v.status == "ok" and v.label == "Exits on the swing plane, same line as going back"
    assert v.measurements["exit_vs_backswing"] == pytest.approx(-0.18, abs=1e-3)
    assert v.frame == 50


@pytest.mark.parametrize("inside_by, status, label", [
    (0.3, "ok", "Exits on the swing plane"),
    (0.9, "warn", "Exits slightly steep"),
    (1.3, "warn", "Exits steep"),  # past the red line, but Watch at most
    (-0.56, "ok", "Exits on the swing plane"),  # Tiger: 28 cm past the ball; pros often exit a little flat
    (-0.85, "warn", "Exits slightly flat"),
    (-1.2, "warn", "Exits flat"),
])
def test_shaft_bands(inside_by, status, label):
    v = run(inside_by=inside_by, back=None)
    assert v.rows[0].status == status and label.lower() in v.label.lower()
    assert v.measurements["shaft_inside_ball"] == pytest.approx(inside_by, abs=1e-3)


@pytest.mark.parametrize("back, status, label", [
    (0.1, "ok", "same line as going back"),
    (-0.45, "ok", "same line as going back"),  # a club golfer's ~50%: fine after impact
    (-0.8, "warn", "slightly steeper than going back"),
    (0.68, "ok", "same line as going back"),  # Tiger: 34 cm flatter; flatter gets more room
    (1.1, "warn", "slightly flatter than going back"),
    (1.5, "warn", "flatter than going back"),
    (-1.17, "warn", "steeper than going back"),  # the amateur swing: laid off going back (Watch at most)
])
def test_same_line_bands(back, status, label):
    v = run(inside_by=0.0, back=back)
    row = v.rows[1]
    assert row.status == status and row.note.lower() == label.lower()
    assert row.fix == "none (a watch item only)" and v.status != "flag"  # the follow-through is never Fix


def test_without_halfway_back_shaft_only():
    v = run(back=None)
    assert v.status == "ok"
    assert v.rows[1].status == "error" and "Mark halfway back" in v.rows[1].note
    assert v.measurements["exit_vs_backswing"] is None


def test_rows_have_units():
    v = run(inside_by=0.0, back=-1.0)
    assert v.rows[1].value == "50 cm steeper"
    assert v.rows[1].good == "up to 30 cm steeper or 45 cm flatter at the ball"


def test_left_handed_mirror_matches():
    for x, b in ((0.02, 0.2), (1.0, -1.0), (-0.4, 0.1)):
        right, left = run(x, b), run(x, b, mirror=True)
        assert left.label == right.label
        for key in ("shaft_inside_ball", "exit_vs_backswing"):
            assert left.measurements[key] == pytest.approx(right.measurements[key], abs=1e-3)


def test_not_marked_explains_how():
    v = run(marked=False)
    assert v.status == "error" and "Follow-through" in v.summary


def test_key_frame_shows_the_swing_plane_line():
    assert any(o.kind == "line" and o.label == "Swing plane" for o in run().overlays)
