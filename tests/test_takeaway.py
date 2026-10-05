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


SPINE_BEND, KNEE_FLEX = 35.0, 25.0  # degrees at address


def pose(mirror=False, spine_lost=0.0, knee_lost=0.0, legs=True):
    """spine_lost / knee_lost: degrees of spine bend / trail knee flex lost by the
    takeaway (from frame 8, clear of smoothing). legs=False: trail leg not tracked."""
    data = np.full((80, len(LANDMARKS), 4), np.nan)
    trail = "left" if mirror else "right"
    for f in range(80):
        bend, flex = np.radians(SPINE_BEND - (spine_lost if f >= 8 else 0.0)),             np.radians(KNEE_FLEX - (knee_lost if f >= 8 else 0.0))
        sh = HIP + 258.0 * np.array([np.sin(bend), -np.cos(bend)])
        pts = {"left_hip": HIP, "right_hip": HIP, "left_shoulder": sh, "right_shoulder": sh}
        if legs:
            knee = HIP + 230.0 * np.array([np.sin(flex), np.cos(flex)])  # thigh slopes back up to the hip
            pts.update({f"{trail}_knee": knee, f"{trail}_ankle": knee + (0.0, 230.0)})
        for name, p in pts.items():
            x = WIDTH - 1 - p[0] if mirror else p[0]
            data[f, LANDMARK_INDEX[name]] = (x, p[1], 0.0, 0.95)
    return PoseSeq(fps=240.0, width=WIDTH, height=1920, data=data)


ADDR_CLUBHEAD = BALL + (-25, 10)
ADDR_GRIP = np.array([512.0, 852.0])  # the shaft points at the belt buckle (25% up the torso)


def on_line(inside_by):
    """A point partway up the address shaft line, moved inside_by body lengths square
    to it toward the golfer (screen-left here), for the right-handed scene."""
    d = (ADDR_GRIP - ADDR_CLUBHEAD) / np.linalg.norm(ADDR_GRIP - ADDR_CLUBHEAD)
    normal = np.array([-d[1], d[0]])
    if normal[0] > 0:
        normal = -normal
    return ADDR_CLUBHEAD + 0.6 * (ADDR_GRIP - ADDR_CLUBHEAD) + inside_by * SCALE * normal


def run(inside_by=None, mirror=False, config=None, spine_lost=0.0, knee_lost=0.0, legs=True):
    """inside_by: the clubhead's distance from the address shaft line in body lengths
    (+ = golfer's side; None = takeaway not marked). mirror=True flips the whole scene
    for a left-hander."""
    config = copy.deepcopy(config or CONFIG)
    flip = (lambda p: (WIDTH - 1 - float(p[0]), float(p[1]))) if mirror else (lambda p: (float(p[0]), float(p[1])))
    if mirror:
        config["golfer"]["handedness"] = "left"
    checkpoints = {}
    if inside_by is not None:
        checkpoints["takeaway"] = CheckpointMark(frame=20, points={"clubhead": flip(on_line(inside_by))})
    marks = Marks(view="dtl", address_frame=0,
                  points={"ball": flip(BALL), "clubhead": flip(ADDR_CLUBHEAD), "grip": flip(ADDR_GRIP)},
                  checkpoints=checkpoints)
    ctx = SwingContext(view="dtl", pose=pose(mirror, spine_lost, knee_lost, legs), marks=marks, phases=PHASES, scale=SCALE, config=config)
    (v,) = [v for v in run_analyzers(ctx) if v.name == "takeaway"]
    return v


def test_clubhead_on_the_line_is_on_plane():
    v = run(inside_by=0.04)
    assert v.status == "ok" and v.label == "Clubhead on the swing plane"
    assert v.phase == "takeaway"


@pytest.mark.parametrize("inside_by, status, label", [
    (0.15, "ok", "Clubhead on the swing plane"),
    (0.3, "warn", "Clubhead slightly toward you"),
    (-0.45, "warn", "Clubhead slightly toward the ball"),
    (0.6, "flag", "Clubhead too far toward you"),
    (-0.6, "flag", "Clubhead too far toward the ball"),
])
def test_inside_and_outside_tiers(inside_by, status, label):
    v = run(inside_by=inside_by)
    assert v.status == status and v.label == label
    assert v.measurements["clubhead_inside_line"] == pytest.approx(inside_by, abs=1e-3)


def test_row_shows_offset_with_units():
    row = run(inside_by=0.3).rows[0]
    assert row.value == "15 cm toward you"  # 30% of the default 50 cm torso
    assert row.note == "Slightly toward you"
    assert (row.good, row.fix) == ("within 10 cm of the line", "more than 25 cm off")
    assert run(inside_by=-0.6).rows[0].value == "30 cm toward the ball"


def test_only_the_clubhead_is_clicked():
    from swingcheck.models import CHECKPOINT_MARKS
    assert CHECKPOINT_MARKS["dtl"]["takeaway"] == ("clubhead",)
    assert run(inside_by=0.6).label == "Clubhead too far toward you"


def test_tolerance_from_config():
    config = copy.deepcopy(CONFIG)
    config["analyzers"]["takeaway"]["line_tolerance"] = 0.03
    config["analyzers"]["takeaway"]["flag_distance"] = 0.2
    assert run(inside_by=0.04, config=config).status == "warn"
    assert run(inside_by=0.3, config=config).status == "flag"
    config["golfer"]["torso_cm"] = 60
    assert run(inside_by=0.3, config=config).rows[0].value == "18 cm toward you"


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
    assert "in front of your hands" in run(inside_by=0.6).tip
    assert "turning your chest" in run(inside_by=-0.6).tip


def test_body_rows_measure_from_address():
    v = run(inside_by=0.0)
    assert [r.label for r in v.rows] == ["Clubhead vs swing plane", "Spine bend kept", "Back knee bend kept"]
    assert v.rows[1].value == "35° (35° at address)" and v.rows[2].value == "25° (25° at address)"
    assert v.status == "ok" and v.label == "Clubhead on the swing plane" and v.tip == ""


@pytest.mark.parametrize("lost, status, label", [
    (2, "ok", None),            # McIlroy
    (5.5, "ok", None),          # Tiger
    (8, "warn", "Slightly standing up"),
    (14, "flag", "Standing up"),
    (-7, "warn", "Slightly bending over"),
    (-12, "flag", "Bending over"),
])
def test_spine_bend_bands(lost, status, label):
    for mirror in (False, True):
        v = run(inside_by=0.0, spine_lost=lost, mirror=mirror)
        row = v.rows[1]
        assert row.status == status and v.status == status
        assert (row.good, row.fix) == ("up to 6° more upright or 5° more bent", "more than 10° either way")
        if label:
            assert v.label == f"Clubhead on the swing plane, {label.lower()}" and v.tip
        else:
            assert v.label == "Clubhead on the swing plane"


@pytest.mark.parametrize("lost, status, label", [
    (3, "ok", None),            # McIlroy
    (-2, "ok", None),           # Tiger
    (8, "warn", "Back knee slightly straightening"),   # the user's indoor swing
    (11, "warn", "Back knee straightening"),           # the user's latest swing: never red
    (-10, "warn", "Back knee slightly sinking"),
    (-18, "warn", "Back knee sinking"),                # never red
])
def test_trail_knee_bands(lost, status, label):
    for mirror in (False, True):
        v = run(inside_by=0.0, knee_lost=lost, mirror=mirror)
        row = v.rows[2]
        assert row.status == status and v.status == status
        assert row.value.endswith(f"({KNEE_FLEX:.0f}° at address)")
        if label:
            assert v.label == f"Clubhead on the swing plane, {label[0].lower() + label[1:]}" and v.tip
        else:
            assert v.label == "Clubhead on the swing plane"


def test_worst_of_the_three_and_tips_combine():
    v = run(inside_by=0.3, spine_lost=14, knee_lost=8)
    assert v.status == "flag"
    assert v.label == "Clubhead slightly toward you, standing up, back knee slightly straightening"
    assert v.rows[0].status == "warn"  # the plane row keeps its own grade
    assert v.tip.count(".") >= 3


def test_untracked_leg_is_not_measured():
    v = run(inside_by=0.0, legs=False)
    assert v.rows[2].status == "error" and v.rows[2].value == "Not measured"
    assert v.status == "ok"


def test_upright_setup_is_judged_against_the_belt_buckle_line(monkeypatch):
    # Hands high: the address shaft points 65% up the torso, above the belt. Taking the
    # club straight back along that steep shaft line is outside the swing plane, which
    # runs from the clubhead to the top of the belt-buckle zone instead.
    import sys
    here = sys.modules[__name__]
    monkeypatch.setattr(here, "ADDR_GRIP", np.array([560.0, 820.0]))
    on_own_shaft = run(inside_by=0.0)
    assert on_own_shaft.measurements["clubhead_inside_line"] < -0.03  # toward the ball
    # A setup that already points at the belt buckle keeps its own shaft line.
    monkeypatch.setattr(here, "ADDR_GRIP", np.array([512.0, 852.0]))
    assert run(inside_by=0.0).measurements["clubhead_inside_line"] == pytest.approx(0.0, abs=1e-3)
