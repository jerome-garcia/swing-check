import copy

import numpy as np
import pytest

from swingcheck import pose as pose_mod
from swingcheck.analyzers import SwingContext, run_analyzers
from swingcheck.analyzers.dtl_impact import back_edge_x
from swingcheck.config import load_config
from swingcheck.models import LANDMARK_INDEX, LANDMARKS, Marks, PoseSeq
from swingcheck.phases import Phases

CONFIG = load_config()
SCALE = 260.0
H, W = 1920, 1080
PHASES = Phases(address=0, takeaway=10, top=20, early_downswing=30, impact=50)
HIP = np.array([350.0, 1000.0])
BALL = np.array([800.0, 1500.0])


def bent(deg):
    a = np.radians(deg)
    return HIP + SCALE * np.array([np.sin(a), -np.cos(a)])


def pose(impact_bend=35.0, mirror=False):
    data = np.full((60, len(LANDMARKS), 4), np.nan)
    for f in range(60):
        sh = bent(impact_bend if f >= 35 else 35.0)  # well before impact, clear of smoothing
        for name, p in {"left_hip": HIP + (5, 0), "right_hip": HIP - (5, 0),
                        "left_shoulder": sh + (5, 0), "right_shoulder": sh - (5, 0)}.items():
            x = W - 1 - p[0] if mirror else p[0]
            data[f, LANDMARK_INDEX[name]] = (x, p[1], 0.0, 0.95)
    return PoseSeq(fps=240.0, width=W, height=H, data=data)


def body_mask(back_x, mirror=False):
    """A block of 'body' whose rear edge (toward the golfer's back, screen left) is at back_x."""
    m = np.zeros((H, W), np.float32)
    m[600:1500, int(back_x):int(back_x) + 300] = 1.0
    return m[:, ::-1].copy() if mirror else m


def run(monkeypatch, hips_forward=0.0, impact_bend=35.0, mirror=False, config=None):
    """hips_forward: torso lengths the rear of the hips moves toward the ball by impact."""
    config = copy.deepcopy(config or CONFIG)
    if mirror:
        config["golfer"]["handedness"] = "left"
    edges = {0: 300.0, 50: 300.0 + hips_forward * SCALE}
    calls = []

    def fake_image(self, f):
        calls.append(f)
        return np.full((H, W, 3), f, np.uint8)

    monkeypatch.setattr(SwingContext, "image", fake_image)
    monkeypatch.setattr(pose_mod, "segment_frame", lambda img, cfg: body_mask(edges[int(img[0, 0, 0])], mirror))
    flip = (lambda p: (W - 1 - float(p[0]), float(p[1]))) if mirror else (lambda p: (float(p[0]), float(p[1])))
    marks = Marks(view="dtl", address_frame=0,
                  points={"ball": flip(BALL), "clubhead": flip(BALL + (-20, 5)), "grip": flip((560, 1100))})
    ctx = SwingContext(view="dtl", pose=pose(impact_bend, mirror), marks=marks, phases=PHASES, scale=SCALE, config=config)
    (v,) = [v for v in run_analyzers(ctx) if v.name == "impact"]
    assert sorted(set(calls)) == [0, 50]  # outlines taken on the address and impact frames
    return v


def test_back_edge_finds_rear_of_body():
    m = body_mask(300)
    assert back_edge_x(m, np.array([350.0, 1000.0]), -1.0, 20, 200) == 300


@pytest.mark.parametrize("fwd, status, label", [
    (-0.05, "ok", "Hips stay back"),
    (0.08, "ok", "Hips stay back"),
    (0.13, "warn", "Hips slightly toward the ball"),
    (0.25, "flag", "Hips toward the ball"),
])
def test_hip_bands(monkeypatch, fwd, status, label):
    v = run(monkeypatch, hips_forward=fwd)
    assert v.rows[0].status == status and label.lower() in v.label.lower()
    assert v.measurements["hips_toward_ball"] == pytest.approx(fwd, abs=0.01)


@pytest.mark.parametrize("bend, status, label", [
    (30, "ok", "Posture kept"),        # 5° more upright
    (22, "warn", "Slightly standing up"),
    (15, "flag", "Standing up"),
    (45, "warn", "Slightly dipping"),
    (52, "flag", "Dipping"),
])
def test_posture_bands(monkeypatch, bend, status, label):
    v = run(monkeypatch, impact_bend=bend)
    assert v.rows[1].status == status and label.lower() in v.label.lower()
    assert v.measurements["posture_lost_deg"] == pytest.approx(35 - bend, abs=0.1)


def test_rows_have_units_and_overall_is_worst(monkeypatch):
    v = run(monkeypatch, hips_forward=0.25, impact_bend=30)
    assert v.status == "flag" and v.label == "Hips toward the ball, posture kept"
    assert v.rows[0].value == "13 cm toward the ball"  # 25% of the default 50 cm torso
    assert v.rows[1].value == "30° (35° at address)"


def test_left_handed_mirror_matches(monkeypatch):
    for fwd, bend in ((0.25, 30), (-0.05, 15)):
        right = run(monkeypatch, hips_forward=fwd, impact_bend=bend)
        left = run(monkeypatch, hips_forward=fwd, impact_bend=bend, mirror=True)
        assert left.label == right.label
        assert left.measurements["hips_toward_ball"] == pytest.approx(right.measurements["hips_toward_ball"], abs=0.01)
