import copy

import numpy as np
import pytest

from swingcheck import pose as pose_mod
from swingcheck.analyzers import SwingContext, run_analyzers
from swingcheck.config import load_config
from swingcheck.geometry import angle_between_deg, max_bulge, silhouette_edge, tilt_from_vertical_deg
from swingcheck.models import LANDMARK_INDEX, LANDMARKS, Marks, PoseSeq
from swingcheck.phases import Phases

CONFIG = load_config()
SCALE = 260.0
FRAMES = 40
PHASES = Phases(address=0, takeaway=10, top=20, early_downswing=30, impact=35)


# --- geometry ---------------------------------------------------------------

def test_angle_between():
    assert angle_between_deg((1, 0), (0, 1)) == pytest.approx(90)
    assert angle_between_deg((1, 0), (-1, 0)) == pytest.approx(180)


def test_tilt_from_vertical_signs():
    # Hanging arm leaning toward screen-right (forward = +1) is positive.
    assert tilt_from_vertical_deg((10, 100), forward_sign=1) == pytest.approx(5.71, abs=0.01)
    assert tilt_from_vertical_deg((10, 100), forward_sign=-1) == pytest.approx(-5.71, abs=0.01)
    # Spine pointing up and forward 35 degrees.
    v = (np.sin(np.radians(35)), -np.cos(np.radians(35)))
    assert tilt_from_vertical_deg(v, forward_sign=1, up=True) == pytest.approx(35)


def body_mask(h=800, w=600, bump=0):
    """A slanted torso band; `bump` px of hump added to the back in the middle."""
    yy, xx = np.mgrid[0:h, 0:w]
    # Back edge runs from (200, 600) up to (350, 200); body is to the right of it.
    t = (600 - yy) / 400.0
    back_x = 200 + 150 * t - bump * np.exp(-((t - 0.6) ** 2) / 0.02)
    mask = ((xx >= back_x) & (xx <= back_x + 120) & (yy >= 150) & (yy <= 650)).astype(np.float32)
    return mask


def test_straight_back_has_no_bulge():
    mask = body_mask()
    hip, shoulder = np.array([260.0, 600.0]), np.array([410.0, 200.0])
    outward = np.array([-400.0, -150.0])  # roughly perpendicular, away from the chest
    pts = silhouette_edge(mask, hip, shoulder, outward, np.linspace(0.2, 0.95, 20), 200)
    assert np.isfinite(pts).all()
    assert max_bulge(pts, outward) < 3


def test_hump_is_measured():
    mask = body_mask(bump=25)
    hip, shoulder = np.array([260.0, 600.0]), np.array([410.0, 200.0])
    outward = np.array([-400.0, -150.0])
    pts = silhouette_edge(mask, hip, shoulder, outward, np.linspace(0.2, 0.95, 20), 200)
    assert max_bulge(pts, outward) > 15


def test_edge_skips_points_off_the_body():
    mask = np.zeros((100, 100), np.float32)
    pts = silhouette_edge(mask, (50, 90), (50, 10), (-1, 0), [0.5], 40)
    assert np.isnan(pts).all()


# --- analyzer ---------------------------------------------------------------

def dtl_address_pose(arm_deg=0.0, spine_deg=35.0, knee_flex=30.0):
    """Right-hander, DTL, facing screen-right (ball on the right). Trail side = right."""
    data = np.full((FRAMES, len(LANDMARKS), 4), np.nan)
    hip = np.array([300.0, 700.0])
    torso = SCALE
    s = np.radians(spine_deg)
    shoulder = hip + torso * np.array([np.sin(s), -np.cos(s)])
    a = np.radians(arm_deg)
    wrist = shoulder + 230 * np.array([np.sin(a), np.cos(a)])
    # Knee forward of the hip-ankle line by the flex angle (thigh and shin each 220 px).
    k = np.radians(knee_flex / 2)
    knee = hip + 220 * np.array([np.sin(k), np.cos(k)])
    ankle = knee + 220 * np.array([-np.sin(k), np.cos(k)])
    pts = {"right_shoulder": shoulder, "left_shoulder": shoulder + (5, 0), "right_wrist": wrist,
           "left_wrist": wrist + (5, 0), "right_hip": hip, "left_hip": hip + (5, 0),
           "right_knee": knee, "right_ankle": ankle, "left_knee": knee, "left_ankle": ankle}
    for name, (x, y) in pts.items():
        data[:, LANDMARK_INDEX[name]] = (x, y, 0.0, 0.95)
    return PoseSeq(fps=240.0, width=1080, height=1920, data=data)


def run_address(pose, config=None, mask=None, monkeypatch=None, ball_x=800.0):
    config = copy.deepcopy(config or CONFIG)
    marks = Marks(view="dtl", address_frame=0,
                  points={"ball": (ball_x, 1100.0), "clubhead": (ball_x - 20, 1110.0), "grip": (560.0, 820.0)})
    ctx = SwingContext(view="dtl", pose=pose, marks=marks, phases=PHASES, scale=SCALE, config=config)
    if mask is not None:
        monkeypatch.setattr(SwingContext, "image", lambda self, f: np.zeros((1920, 1080, 3), np.uint8))
        monkeypatch.setattr(pose_mod, "segment_frame", lambda img, cfg: mask)
    (v,) = [v for v in run_analyzers(ctx) if v.name == "address"]
    return v


def test_good_address():
    v = run_address(dtl_address_pose())
    m = v.measurements
    assert m["arm_from_vertical_deg"] == pytest.approx(0, abs=0.5)
    assert m["spine_bend_deg"] == pytest.approx(35, abs=1)
    assert m["knee_flex_deg"] == pytest.approx(30, abs=0.5)
    # No video here, so the back isn't measured; the other checks still pass.
    assert m["back"].startswith("not measured")
    assert v.status == "ok" and v.label == "good"


@pytest.mark.parametrize("kwargs, problem", [
    ({"arm_deg": 18}, "arms reaching out"),
    ({"arm_deg": -18}, "arms too close to body"),
    ({"spine_deg": 20}, "spine too upright"),
    ({"spine_deg": 55}, "spine bent over too far"),
    ({"knee_flex": 5}, "knees too straight"),
    ({"knee_flex": 45}, "knees too much bend"),
])
def test_each_fault_flagged(kwargs, problem):
    v = run_address(dtl_address_pose(**kwargs))
    assert v.status == "flag"
    assert problem in v.label


@pytest.mark.parametrize("kwargs, problem", [
    ({"arm_deg": 12}, "arms slightly reaching out"),
    ({"arm_deg": -12}, "arms slightly close to body"),
    ({"spine_deg": 28}, "spine slightly upright"),
    ({"spine_deg": 48}, "spine slightly bent over"),
    ({"knee_flex": 12}, "knees slightly straight"),
    ({"knee_flex": 38}, "knees slightly too bent"),
])
def test_just_outside_good_range_is_yellow(kwargs, problem):
    v = run_address(dtl_address_pose(**kwargs))
    assert v.status == "warn"
    assert v.label == problem


def test_red_beats_yellow_overall():
    v = run_address(dtl_address_pose(arm_deg=12, spine_deg=20))
    assert v.status == "flag"
    assert {r.label: r.status for r in v.rows}["Arms"] == "warn"


def test_rows_say_how_much_to_adjust():
    v = run_address(dtl_address_pose(arm_deg=12, spine_deg=28, knee_flex=40))
    notes = {r.label: r.note for r in v.rows}
    assert notes["Spine bend"] == "bend 2° more (green 30–45°, red outside 25–50°)"
    assert notes["Knee flex"] == "straighten 5° (green 15–35°, red outside 10–40°)"
    assert notes["Arms"] == "hands 2° too far out (green within ±10°, red past ±15°)"
    assert "Hinge more from the hips" in v.summary
    good = run_address(dtl_address_pose())
    assert {r.label: r.note for r in good.rows}["Spine bend"] == "good bend (green 30–45°, red outside 25–50°)"


def test_target_lines_drawn_at_middle_of_range():
    v = run_address(dtl_address_pose(arm_deg=18, spine_deg=20, knee_flex=5))
    dashed = [o for o in v.overlays if o.kind == "dashed"]
    assert len(dashed) == 3
    spine, arm, thigh = dashed
    # Spine aim: 37.5 degrees forward of vertical, from the hips.
    assert tilt_from_vertical_deg(np.subtract(spine.points[1], spine.points[0]), 1, up=True) == pytest.approx(37.5)
    # Arm aim: straight down from the shoulder.
    assert spine.points[0] != arm.points[0] and arm.points[0][0] == pytest.approx(arm.points[1][0])
    # Knee aim: thigh swung so the knee flex is 25 degrees, hip behind the knee.
    knee = np.array(thigh.points[0])
    ankle = dtl_address_pose(knee_flex=5).data[0, LANDMARK_INDEX["right_ankle"], :2]
    flex = 180 - angle_between_deg(np.subtract(thigh.points[1], knee), ankle - knee)
    assert flex == pytest.approx(25)
    assert thigh.points[1][0] < knee[0]
    # Nothing out of range: no target lines.
    assert not [o for o in run_address(dtl_address_pose()).overlays if o.kind == "dashed"]


def test_back_bulge_from_silhouette(monkeypatch):
    pose = dtl_address_pose()
    hip = pose.data[0, LANDMARK_INDEX["right_hip"], :2]
    sh = pose.data[0, LANDMARK_INDEX["right_shoulder"], :2]
    yy, xx = np.mgrid[0:1920, 0:1080]
    # Signed distance behind the spine line (positive = toward the back, away from the ball).
    d = hip - sh
    n = np.array([d[1], -d[0]]) / np.linalg.norm(d)
    if n[0] > 0:
        n = -n
    rel = np.stack([xx - hip[0], yy - hip[1]], -1)
    along = rel @ (-(d) / np.linalg.norm(d))
    behind = rel @ n
    t = along / np.linalg.norm(d)

    def mask_with(hump):
        back = 40 + hump * np.exp(-((t - 0.6) ** 2) / 0.02)
        return ((behind <= back) & (behind >= -80) & (t > -0.1) & (t < 1.1)).astype(np.float32)

    flat = run_address(pose, mask=mask_with(0), monkeypatch=monkeypatch)
    assert flat.measurements["back"] == "straight"
    humped = run_address(pose, mask=mask_with(40), monkeypatch=monkeypatch)
    assert humped.measurements["back"] == "rounded / hump"
    assert humped.measurements["back_bulge"] > CONFIG["analyzers"]["address"]["back_bulge_max"]
    assert humped.status == "flag"


@pytest.mark.parametrize("kwargs", [{"arm_deg": 18}, {"arm_deg": -12, "spine_deg": 22, "knee_flex": 40}])
def test_left_handed_mirror_matches(kwargs):
    right = run_address(dtl_address_pose(**kwargs))
    pose = dtl_address_pose(**kwargs)
    pose.data[:, :, 0] = 1079 - pose.data[:, :, 0]
    for a, b in [("left_shoulder", "right_shoulder"), ("left_hip", "right_hip"), ("left_wrist", "right_wrist"),
                 ("left_knee", "right_knee"), ("left_ankle", "right_ankle")]:
        ia, ib = LANDMARK_INDEX[a], LANDMARK_INDEX[b]
        pose.data[:, [ia, ib]] = pose.data[:, [ib, ia]]
    config = copy.deepcopy(CONFIG)
    config["golfer"]["handedness"] = "left"
    left = run_address(pose, config=config, ball_x=1079 - 800.0)
    assert left.label == right.label
    for key in ("arm_from_vertical_deg", "spine_bend_deg", "knee_flex_deg"):
        assert left.measurements[key] == pytest.approx(right.measurements[key], abs=0.2), key
