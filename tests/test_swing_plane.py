import copy

import numpy as np
import pytest

from swingcheck.analyzers import SwingContext, run_analyzers
from swingcheck.config import load_config
from swingcheck.models import LANDMARK_INDEX, LANDMARKS, Marks, PoseSeq
from swingcheck.phases import Phases

CONFIG = load_config()
FRAMES = 100
PHASES = Phases(address=10, takeaway=30, top=50, early_downswing=70, impact=80)
SCALE = 260.0
WIDTH = 720

# Right-handed DTL layout (see test_geometry): ball low right, lines rising up-left.
BALL = np.array([600.0, 1180.0])
CLUBHEAD = np.array([575.0, 1190.0])
SHAFT_DIR = np.array([-230.0, -290.0])
GRIP = CLUBHEAD + SHAFT_DIR
SHOULDER = np.array([270.0, 480.0])  # trail shoulder at address


def toward(frac):
    """A point between the shaft line (0) and the shoulder line (1), 400 px out from the ball."""
    a = SHAFT_DIR / np.linalg.norm(SHAFT_DIR)
    b = (SHOULDER - BALL) / np.linalg.norm(SHOULDER - BALL)
    d = (1 - frac) * a + frac * b
    return BALL + 400 * d / np.linalg.norm(d)


def dtl_pose(takeaway, top, early, wrist_offset=(0.0, 0.0), mirror=False):
    """Hands at address on the shaft line (plus `wrist_offset`), then at the given checkpoint points."""
    data = np.full((FRAMES, len(LANDMARKS), 4), np.nan)
    address_hands = BALL + 0.95 * SHAFT_DIR + np.asarray(wrist_offset)  # on the ball-anchored shaft line
    keys = {0: address_hands, PHASES.address: address_hands, PHASES.takeaway: takeaway + wrist_offset,
            PHASES.top: top + wrist_offset, PHASES.early_downswing: early + wrist_offset,
            PHASES.impact: address_hands, FRAMES - 1: address_hands}
    frames = sorted(keys)
    xs = np.interp(np.arange(FRAMES), frames, [keys[f][0] for f in frames])
    ys = np.interp(np.arange(FRAMES), frames, [keys[f][1] for f in frames])
    ones = np.ones(FRAMES)
    body = {"right_shoulder": SHOULDER, "left_shoulder": SHOULDER + (60, 10),
            "right_hip": SHOULDER + (40, 260), "left_hip": SHOULDER + (90, 260)}
    for name, (x, y) in body.items():
        data[:, LANDMARK_INDEX[name]] = np.stack([x * ones, y * ones, 0 * ones, 0.95 * ones], 1)
    for name in ("left_wrist", "right_wrist"):
        data[:, LANDMARK_INDEX[name]] = np.stack([xs, ys, 0 * ones, 0.95 * ones], 1)
    if mirror:
        data[:, :, 0] = WIDTH - 1 - data[:, :, 0]
        for a, b in [("left_shoulder", "right_shoulder"), ("left_hip", "right_hip"), ("left_wrist", "right_wrist")]:
            ia, ib = LANDMARK_INDEX[a], LANDMARK_INDEX[b]
            data[:, [ia, ib]] = data[:, [ib, ia]]
    return PoseSeq(fps=240.0, width=WIDTH, height=1280, data=data)


def run(pose, mirror=False, config=None):
    config = copy.deepcopy(config or CONFIG)
    config["pose"]["smoothing_ms"] = 0
    def m(p):
        return (WIDTH - 1 - p[0], p[1]) if mirror else (p[0], p[1])
    if mirror:
        config["golfer"]["handedness"] = "left"
    marks = Marks(view="dtl", address_frame=10,
                  points={"ball": m(BALL), "clubhead": m(CLUBHEAD), "grip": m(GRIP)})
    ctx = SwingContext(view="dtl", pose=pose, marks=marks, phases=PHASES, scale=SCALE, config=config)
    (verdict,) = [v for v in run_analyzers(ctx) if v.name == "swing_plane"]
    return verdict


def test_on_plane_everywhere():
    v = run(dtl_pose(toward(0.5), toward(0.6), toward(0.5)))
    assert v.status == "ok"
    assert v.label == "on plane / on plane / on plane"


def test_over_the_top_flagged():
    v = run(dtl_pose(toward(0.5), toward(0.6), toward(1.6)))
    assert v.status == "flag"
    assert v.measurements["early_downswing_zone"] == "steep"
    assert v.measurements["early_downswing_shoulder_line_margin"] < 0
    assert "over the top" in v.summary


def test_stuck_under_flagged():
    v = run(dtl_pose(toward(0.5), toward(0.6), toward(-0.6)))
    assert v.status == "flag" and v.measurements["early_downswing_zone"] == "shallow"


def test_off_plane_takeaway_only_warns():
    v = run(dtl_pose(toward(-0.6), toward(0.6), toward(0.5)))
    assert v.status == "warn"
    assert v.label == "shallow / on plane / on plane"


def test_wrist_offset_at_address_is_calibrated_out():
    # Wrists sit 25 px outside the shaft line at address; the swing itself is on plane.
    n = np.array([SHAFT_DIR[1], -SHAFT_DIR[0]]) / np.linalg.norm(SHAFT_DIR)
    outward = n if np.dot(n, SHOULDER - BALL) < 0 else -n
    offset = 25 * outward
    pose = dtl_pose(toward(0.05), toward(0.6), toward(0.5), wrist_offset=offset)
    assert run(pose).measurements["takeaway_zone"] == "on plane"
    assert run(pose).measurements["address_wrist_offset_from_shaft_line"] == pytest.approx(-25 / SCALE, abs=1e-3)
    config = copy.deepcopy(CONFIG)
    config["analyzers"]["swing_plane"]["calibrate_hands_to_shaft_line"] = False
    assert run(pose, config=config).measurements["takeaway_zone"] == "shallow"


def test_left_hander_mirror_matches():
    args = (toward(-0.6), toward(0.6), toward(1.6))
    right = run(dtl_pose(*args))
    left = run(dtl_pose(*args, mirror=True), mirror=True)
    assert left.label == right.label
    assert left.measurements["early_downswing_shoulder_line_margin"] == pytest.approx(
        right.measurements["early_downswing_shoulder_line_margin"], abs=1e-3)


def test_tolerance_from_config():
    pose = dtl_pose(toward(0.5), toward(0.6), toward(1.05))  # just past the shoulder line
    assert run(pose).measurements["early_downswing_zone"] == "on plane"
    config = copy.deepcopy(CONFIG)
    config["analyzers"]["swing_plane"]["tolerance"] = 0.0
    assert run(pose, config=config).measurements["early_downswing_zone"] == "steep"


def test_missing_trail_shoulder_is_an_error_verdict():
    pose = dtl_pose(toward(0.5), toward(0.6), toward(0.5))
    pose.data[:, LANDMARK_INDEX["right_shoulder"]] = np.nan
    v = run(pose)
    assert v.status == "error"


def test_overlays_include_both_plane_lines():
    v = run(dtl_pose(toward(0.5), toward(0.6), toward(0.5)))
    labels = {o.label for o in v.overlays if o.kind == "ray"}
    assert labels == {"shaft plane", "shoulder plane"}
