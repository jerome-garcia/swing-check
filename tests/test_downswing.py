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


SPINE_BEND = 35.0  # degrees at address


def pose(mirror=False, spine_lost=0.0):
    """spine_lost: degrees of spine bend lost by the downswing frame (from frame 45)."""
    data = np.full((80, len(LANDMARKS), 4), np.nan)
    for f in range(80):
        bend = np.radians(SPINE_BEND - (spine_lost if f >= 45 else 0.0))
        sh = HIP + 258.0 * np.array([np.sin(bend), -np.cos(bend)])
        for name, p in {"left_hip": HIP, "right_hip": HIP, "left_shoulder": sh, "right_shoulder": sh}.items():
            x = WIDTH - 1 - p[0] if mirror else p[0]
            data[f, LANDMARK_INDEX[name]] = (x, p[1], 0.0, 0.95)
    return PoseSeq(fps=240.0, width=WIDTH, height=1920, data=data)


def on_line(under):
    """A point partway up the address shaft line, moved `under` torso lengths square to it toward the golfer."""
    d = (ADDR_GRIP - ADDR_CLUBHEAD) / np.linalg.norm(ADDR_GRIP - ADDR_CLUBHEAD)
    normal = np.array([-d[1], d[0]])
    if normal[0] > 0:
        normal = -normal
    return ADDR_CLUBHEAD + 0.6 * (ADDR_GRIP - ADDR_CLUBHEAD) + under * SCALE * normal


def run(under=0.15, takeaway=0.0, mirror=False, config=None, marked=True, spine_lost=0.0):
    config = copy.deepcopy(config or CONFIG)
    flip = (lambda p: (WIDTH - 1 - float(p[0]), float(p[1]))) if mirror else (lambda p: (float(p[0]), float(p[1])))
    if mirror:
        config["golfer"]["handedness"] = "left"
    checkpoints = {}
    if takeaway is not None:
        checkpoints["takeaway"] = CheckpointMark(frame=20, points={"clubhead": flip(on_line(takeaway)), "grip": flip(HANDS)})
    if marked:
        checkpoints["downswing"] = CheckpointMark(frame=55, points={"clubhead": flip(on_line(under))})
    marks = Marks(view="dtl", address_frame=0,
                  points={"ball": flip(BALL), "clubhead": flip(ADDR_CLUBHEAD), "grip": flip(ADDR_GRIP)},
                  checkpoints=checkpoints)
    ctx = SwingContext(view="dtl", pose=pose(mirror, spine_lost), marks=marks, phases=PHASES, scale=SCALE, config=config)
    (v,) = [v for v in run_analyzers(ctx) if v.name == "downswing"]
    return v


def test_on_plane_and_shallowed():
    v = run(under=0.15, takeaway=-0.04)  # McIlroy-like
    assert v.status == "ok" and v.label == "Clubhead on the swing plane, flatter than going back"
    assert v.measurements["shallowing_vs_takeaway"] == pytest.approx(0.19, abs=1e-3)
    assert v.frame == 55


@pytest.mark.parametrize("under, status, label", [
    (0.2, "ok", "Clubhead on the swing plane"),
    (-0.01, "ok", "Clubhead on the swing plane"),  # Tiger: on the line, a hair above
    (-0.08, "ok", "Clubhead on the swing plane"),  # within a click of the line
    (-0.12, "warn", "Clubhead slightly above the swing plane"),
    (-0.18, "warn", "Clubhead slightly above the swing plane"),  # inside the grey line
    (-0.28, "warn", "Clubhead slightly above the swing plane"),  # past the grey line, still yellow
    (-0.35, "flag", "Clubhead above the swing plane"),
    (0.55, "warn", "Clubhead well under the swing plane"),
    (0.9, "flag", "Clubhead too far under the swing plane"),
])
def test_plane_bands(under, status, label):
    v = run(under=under, takeaway=None)
    assert v.rows[0].status == status and label.lower() in v.label.lower()
    assert v.measurements["clubhead_under_line"] == pytest.approx(under, abs=1e-3)


@pytest.mark.parametrize("takeaway, status, label", [
    (0.0, "ok", "flatter than going back"),
    (0.25, "warn", "slightly steeper than going back"),
    (0.5, "flag", "steeper than going back"),
])
def test_shallowing_bands(takeaway, status, label):
    # Same downswing position (on plane); only the takeaway differs. An inside takeaway
    # followed by an on-plane downswing is the over-the-top loop.
    v = run(under=0.2, takeaway=takeaway)
    row = v.rows[1]
    assert row.label == "Vs your takeaway" and row.status == status and row.note.lower() == label.lower()
    assert v.status == max(["ok", status], key={"ok": 0, "warn": 1, "flag": 2}.get)


def test_without_takeaway_marks_plane_only():
    v = run(under=0.2, takeaway=None)
    assert v.status == "ok"
    assert v.rows[1].status == "error" and "Mark the takeaway" in v.rows[1].note
    assert v.measurements["shallowing_vs_takeaway"] is None


def test_rows_have_units():
    v = run(under=0.2, takeaway=0.5)
    assert v.rows[0].value == "10 cm under the line"
    assert v.rows[1].value == "15 cm steeper"
    assert v.rows[1].value.endswith(" cm steeper") or v.rows[1].value.endswith(" cm flatter")


def test_left_handed_mirror_matches():
    for under, take in ((0.15, -0.04), (-0.3, 0.5), (0.9, 0.0)):
        right, left = run(under, take), run(under, take, mirror=True)
        assert left.label == right.label
        for key in ("clubhead_under_line", "shallowing_vs_takeaway"):
            assert left.measurements[key] == pytest.approx(right.measurements[key], abs=1e-3)


def test_not_marked_explains_how():
    v = run(marked=False)
    assert v.status == "error" and "Downswing" in v.summary


def test_only_the_clubhead_is_clicked():
    from swingcheck.models import CHECKPOINT_MARKS
    assert CHECKPOINT_MARKS["dtl"]["downswing"] == ("clubhead",)


def test_dashed_line_joins_takeaway_and_downswing_clubheads():
    v = run(under=0.15, takeaway=-0.04)
    (dash,) = [o for o in v.overlays if o.kind == "dashed"]
    assert dash.points[0] == pytest.approx(on_line(-0.04)) and dash.points[1] == pytest.approx(on_line(0.15))


def test_takeaway_clubhead_is_a_solid_dot_in_its_own_color():
    from swingcheck.analyzers import PAST_COLOR
    v = run(under=0.15, takeaway=-0.04)
    (dot,) = [o for o in v.overlays if o.kind == "circle" and o.points[0] == pytest.approx(on_line(-0.04))]
    assert dot.color == PAST_COLOR  # a clubhead (solid circle) in the earlier-checkpoint color



@pytest.mark.parametrize("lost, status, extra", [
    (1, "ok", None),                       # McIlroy
    (-2, "ok", None),                      # Tiger, a little more bent
    (6, "warn", "slightly standing up"),   # the user's latest swing
    (12, "flag", "standing up"),
])
def test_spine_bend_kept_coming_down(lost, status, extra):
    for mirror in (False, True):
        v = run(under=0.15, takeaway=-0.04, spine_lost=lost, mirror=mirror)  # club green
        row = v.rows[-1]
        assert row.label == "Spine bend kept" and row.status == status
        assert row.good == "up to 5° either way" and row.fix == "more than 10° either way"
        assert v.status == status
        assert v.label == "Clubhead on the swing plane, flatter than going back" + (f", {extra}" if extra else "")
        assert any(o.label == "Address spine" for o in v.overlays) == (status != "ok")
