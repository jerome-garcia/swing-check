import copy

import numpy as np
import pytest

from swingcheck.analyzers import MissingData, SwingContext, run_analyzers
from swingcheck.analyzers.dtl_swing_plane import shaft_angle_deg, torso_crossing
from swingcheck.config import load_config
from swingcheck.models import LANDMARK_INDEX, LANDMARKS, Marks, PoseSeq
from swingcheck.phases import Phases

CONFIG = load_config()
PHASES = Phases(address=0, takeaway=10, top=20, early_downswing=30, impact=35)
HIP = np.array([300.0, 700.0])
SHOULDER = np.array([450.0, 490.0])  # torso leaning toward the ball (screen-right)
CLUBHEAD = np.array([700.0, 1150.0])


def grip_for(fraction, length=330.0):
    """A grip point on the line from the clubhead toward the torso point at `fraction` (0 hip, 1 shoulder)."""
    target = HIP + fraction * (SHOULDER - HIP)
    d = (target - CLUBHEAD) / np.linalg.norm(target - CLUBHEAD)
    return CLUBHEAD + length * d


def pose(mirror=False, width=1080):
    data = np.full((40, len(LANDMARKS), 4), np.nan)
    pts = {"left_hip": HIP + (8, 0), "right_hip": HIP, "left_shoulder": SHOULDER + (8, 0), "right_shoulder": SHOULDER}
    for name, (x, y) in pts.items():
        data[:, LANDMARK_INDEX[name]] = (x, y, 0.0, 0.95)
    if mirror:
        data[:, :, 0] = width - 1 - data[:, :, 0]
    return PoseSeq(fps=240.0, width=width, height=1920, data=data)


def run(grip, clubhead=CLUBHEAD, mirror=False, config=None, width=1080):
    config = copy.deepcopy(config or CONFIG)
    flip = (lambda p: (width - 1 - p[0], p[1])) if mirror else (lambda p: (float(p[0]), float(p[1])))
    if mirror:
        config["golfer"]["handedness"] = "left"
    marks = Marks(view="dtl", address_frame=0,
                  points={"ball": flip(clubhead + (20, 5)), "clubhead": flip(clubhead), "grip": flip(grip)})
    ctx = SwingContext(view="dtl", pose=pose(mirror, width), marks=marks, phases=PHASES, scale=260.0, config=config)
    (v,) = [v for v in run_analyzers(ctx) if v.name == "swing_plane"]
    return v


def test_geometry_helpers():
    assert shaft_angle_deg((100, 100), (0, 0)) == pytest.approx(45)
    assert shaft_angle_deg((100, 100), (200, 0)) == pytest.approx(45)  # either direction
    assert torso_crossing(CLUBHEAD, grip_for(0.3), HIP, SHOULDER) == pytest.approx(0.3)
    assert torso_crossing(CLUBHEAD, grip_for(-0.2), HIP, SHOULDER) == pytest.approx(-0.2)
    with pytest.raises(MissingData):
        torso_crossing((0, 0), (0, 10), (5, 0), (5, 10))  # parallel to the spine


def test_points_at_belt_buckle():
    v = run(grip_for(0.3))
    assert v.status == "ok" and v.label == "Points at belt buckle"
    assert v.measurements["alignment"].startswith("Points at belt buckle.")
    assert v.measurements["crosses_torso_at"] == pytest.approx(0.3, abs=0.02)  # body center is 4 px off the trail side
    assert 45 <= v.measurements["shaft_angle_deg"] <= 65


def test_points_above_belt_is_flagged():
    v = run(grip_for(0.8))
    assert v.status == "flag" and "Points above belt" in v.label
    assert "too close" in v.summary and "too close" in v.measurements["alignment"]


def test_points_below_belt_is_flagged():
    v = run(grip_for(-0.3))
    assert v.status == "flag" and "Points below belt" in v.label
    assert "too far" in v.summary


def test_points_just_off_the_belt_is_yellow():
    v = run(grip_for(0.5))
    assert v.status == "warn" and "Points just above belt" in v.label
    assert "slightly upright" in v.summary
    v = run(grip_for(-0.05))
    assert v.status == "warn" and "Points just below belt" in v.label


def test_alignment_row_has_units():
    row = run(grip_for(0.3)).rows[0]
    assert row.value in ("29% up the torso", "30% up the torso")  # 0.3 of the torso, give or take rounding
    assert "cm above hip center · Points at belt buckle (green 0%–45%, red below -10% or above 60%)" in row.note


def test_angle_has_its_own_bands():
    # A long, flat shaft that still points at the belt.
    far_clubhead = np.array([1050.0, 1000.0])
    target = HIP + 0.25 * (SHOULDER - HIP)
    grip = far_clubhead + 0.5 * (target - far_clubhead)
    v = run(grip, clubhead=far_clubhead)
    angle = v.measurements["shaft_angle_deg"]
    assert angle < 45
    expected = "warn" if angle >= 40 else "flag"
    assert {r.label: r.status for r in v.rows}["Shaft angle"] == expected
    assert v.status == expected
    assert "Points at belt buckle" in v.label


def test_ranges_come_from_config():
    config = copy.deepcopy(CONFIG)
    config["analyzers"]["swing_plane"]["belt_max"] = 0.2
    assert run(grip_for(0.3), config=config).status == "warn"
    config["analyzers"]["swing_plane"]["belt_watch_max"] = 0.25
    assert run(grip_for(0.3), config=config).status == "flag"


def test_left_handed_mirror_matches():
    for f in (0.3, 0.8, -0.3):
        right, left = run(grip_for(f)), run(grip_for(f), mirror=True)
        assert left.label == right.label
        assert left.measurements["crosses_torso_at"] == pytest.approx(right.measurements["crosses_torso_at"], abs=0.01)
        assert left.measurements["shaft_angle_deg"] == pytest.approx(right.measurements["shaft_angle_deg"], abs=0.1)


def test_overlapping_marks_are_an_error_not_a_crash():
    v = run(CLUBHEAD + (1, 1))
    assert v.status == "error"
