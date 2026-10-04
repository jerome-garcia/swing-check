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
ADDR_CLUBHEAD = BALL + (-25, 10)
ADDR_GRIP = np.array([560.0, 820.0])
HANDS = np.array([520.0, 760.0])


def pose(mirror=False):
    data = np.full((80, len(LANDMARKS), 4), np.nan)
    for name, p in {"left_hip": HIP, "right_hip": HIP}.items():
        x = WIDTH - 1 - p[0] if mirror else p[0]
        data[:, LANDMARK_INDEX[name]] = (x, p[1], 0.0, 0.95)
    return PoseSeq(fps=240.0, width=WIDTH, height=1920, data=data)


def on_line(under):
    """A point partway up the address shaft line, moved `under` torso lengths square to it toward the golfer."""
    d = (ADDR_GRIP - ADDR_CLUBHEAD) / np.linalg.norm(ADDR_GRIP - ADDR_CLUBHEAD)
    normal = np.array([-d[1], d[0]])
    if normal[0] > 0:
        normal = -normal
    return ADDR_CLUBHEAD + 0.6 * (ADDR_GRIP - ADDR_CLUBHEAD) + under * SCALE * normal


def run(under=0.15, takeaway=0.0, mirror=False, config=None, marked=True):
    config = copy.deepcopy(config or CONFIG)
    flip = (lambda p: (WIDTH - 1 - float(p[0]), float(p[1]))) if mirror else (lambda p: (float(p[0]), float(p[1])))
    if mirror:
        config["golfer"]["handedness"] = "left"
    checkpoints = {}
    if takeaway is not None:
        checkpoints["takeaway"] = CheckpointMark(frame=20, points={"clubhead": flip(on_line(takeaway)), "grip": flip(HANDS)})
    if marked:
        checkpoints["downswing"] = CheckpointMark(frame=55, points={"clubhead": flip(on_line(under)), "grip": flip(HANDS)})
    marks = Marks(view="dtl", address_frame=0,
                  points={"ball": flip(BALL), "clubhead": flip(ADDR_CLUBHEAD), "grip": flip(ADDR_GRIP)},
                  checkpoints=checkpoints)
    ctx = SwingContext(view="dtl", pose=pose(mirror), marks=marks, phases=PHASES, scale=SCALE, config=config)
    (v,) = [v for v in run_analyzers(ctx) if v.name == "downswing"]
    return v


def test_on_plane_and_shallowed():
    v = run(under=0.15, takeaway=-0.04)  # McIlroy-like
    assert v.status == "ok" and v.label == "Club down the swing plane, shallowed"
    assert v.measurements["shallowing_vs_takeaway"] == pytest.approx(0.19, abs=1e-3)
    assert v.frame == 55


@pytest.mark.parametrize("under, status, label", [
    (0.2, "ok", "Club down the swing plane"),
    (-0.1, "warn", "Clubhead slightly above the swing plane"),
    (-0.3, "flag", "Clubhead above the swing plane"),
    (0.55, "warn", "Clubhead well under the swing plane"),
    (0.9, "flag", "Clubhead stuck under the swing plane"),
])
def test_plane_bands(under, status, label):
    v = run(under=under, takeaway=None)
    assert v.rows[0].status == status and label.lower() in v.rows[0].note
    assert v.measurements["clubhead_under_line"] == pytest.approx(under, abs=1e-3)


@pytest.mark.parametrize("takeaway, status, label", [
    (0.0, "ok", "shallowed"),
    (0.25, "warn", "slightly steeper than the takeaway"),
    (0.5, "flag", "steeper than the takeaway"),
])
def test_shallowing_bands(takeaway, status, label):
    # Same downswing position (on plane); only the takeaway differs. An inside takeaway
    # followed by an on-plane downswing is the over-the-top loop.
    v = run(under=0.2, takeaway=takeaway)
    row = v.rows[1]
    assert row.label == "Shallowing" and row.status == status and label in row.note
    assert v.status == max(["ok", status], key={"ok": 0, "warn": 1, "flag": 2}.get)


def test_without_takeaway_marks_plane_only():
    v = run(under=0.2, takeaway=None)
    assert v.status == "ok"
    assert v.rows[1].status == "error" and "mark the takeaway" in v.rows[1].note
    assert v.measurements["shallowing_vs_takeaway"] is None


def test_rows_have_units():
    v = run(under=0.2, takeaway=0.5)
    assert v.rows[0].value == "≈10 cm under"
    assert v.rows[1].value == "≈15 cm steeper"
    assert "of torso length" in v.rows[1].note


def test_left_handed_mirror_matches():
    for under, take in ((0.15, -0.04), (-0.3, 0.5), (0.9, 0.0)):
        right, left = run(under, take), run(under, take, mirror=True)
        assert left.label == right.label
        for key in ("clubhead_under_line", "shallowing_vs_takeaway"):
            assert left.measurements[key] == pytest.approx(right.measurements[key], abs=1e-3)


def test_not_marked_explains_how():
    v = run(marked=False)
    assert v.status == "error" and "Downswing" in v.summary
