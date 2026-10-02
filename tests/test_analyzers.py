import copy

import numpy as np
import pytest

from swingcheck import analyzers
from swingcheck.analyzers import REGISTRY, SwingContext, Verdict, analyzers_for, register, run_analyzers
from swingcheck.config import load_config
from swingcheck.models import LANDMARK_INDEX, LANDMARKS, Marks, PoseSeq
from swingcheck.phases import Phases

CONFIG = load_config()
FRAMES = 100
PHASES = Phases(address=10, takeaway=30, top=50, early_downswing=70, impact=80)
TORSO = 260.0
BALL_X = 540.0


def face_on_pose(hands_dx=0.0, hip_dx=0.0, head_dx=0.0, mirror=False):
    """Face-on golfer standing still at address; at impact (frame 80 on) the
    hands, hips and head are shifted by the given amounts (pixels, + = screen-right)."""
    width = 1080
    data = np.full((FRAMES, len(LANDMARKS), 4), np.nan)
    base = {
        "nose": (540, 300), "left_ear": (525, 290), "right_ear": (555, 290),
        "left_shoulder": (480, 400), "right_shoulder": (600, 400),
        "left_hip": (500, 660), "right_hip": (580, 660),
        "left_wrist": (535, 760), "right_wrist": (545, 760),
    }
    groups = {"hands": ("left_wrist", "right_wrist"), "hips": ("left_hip", "right_hip"),
              "head": ("nose", "left_ear", "right_ear")}
    shift = {"hands": hands_dx, "hips": hip_dx, "head": head_dx}
    for name, (x, y) in base.items():
        xs = np.full(FRAMES, float(x))
        for group, names in groups.items():
            if name in names:
                xs[PHASES.impact:] += shift[group]
        if mirror:
            xs = width - 1 - xs
        data[:, LANDMARK_INDEX[name]] = np.stack([xs, np.full(FRAMES, float(y)), np.zeros(FRAMES), np.full(FRAMES, 0.95)], 1)
    if mirror:  # a left-hander's left/right landmarks swap sides of the screen
        for a, b in [("left_wrist", "right_wrist"), ("left_hip", "right_hip"), ("left_ear", "right_ear"),
                     ("left_shoulder", "right_shoulder")]:
            ia, ib = LANDMARK_INDEX[a], LANDMARK_INDEX[b]
            data[:, [ia, ib]] = data[:, [ib, ia]]
    return PoseSeq(fps=240.0, width=width, height=1920, data=data)


def run_fo(pose, mirror=False, config=None):
    config = copy.deepcopy(config or CONFIG)
    config["pose"]["smoothing_ms"] = 0  # keep the step change crisp
    if mirror:
        config["golfer"]["handedness"] = "left"
    ball = (1080 - 1 - BALL_X) if mirror else BALL_X
    marks = Marks(view="fo", address_frame=10, points={"ball": (ball, 1000.0)})
    ctx = SwingContext(view="fo", pose=pose, marks=marks, phases=PHASES, scale=TORSO, config=config)
    return {v.name: v for v in run_analyzers(ctx)}


def test_builtin_fo_analyzers_registered():
    names = {a.name for a in analyzers_for("fo", CONFIG)}
    assert {"hands_at_impact", "weight_shift", "head_drift"} <= names
    assert all(a.view == "fo" for a in analyzers_for("fo", CONFIG))


def test_good_impact_all_ok():
    # Right-hander, target screen-right: hands, hips forward; head steady.
    v = run_fo(face_on_pose(hands_dx=0.2 * TORSO, hip_dx=0.25 * TORSO, head_dx=0.0))
    assert v["hands_at_impact"].label == "ahead" and v["hands_at_impact"].status == "ok"
    assert v["weight_shift"].status == "ok"
    assert v["head_drift"].label == "steady"


def test_scoop_and_hang_back_flagged():
    v = run_fo(face_on_pose(hands_dx=-0.15 * TORSO, hip_dx=0.02 * TORSO, head_dx=-0.2 * TORSO))
    assert v["hands_at_impact"].label == "behind" and v["hands_at_impact"].status == "flag"
    assert v["weight_shift"].status == "flag"
    assert v["head_drift"].status == "flag"
    assert v["hands_at_impact"].measurements["hands_ahead_at_impact"] == pytest.approx(-0.15, abs=1e-3)


def test_level_hands_warn():
    v = run_fo(face_on_pose(hands_dx=0.02 * TORSO))
    assert v["hands_at_impact"].label == "level" and v["hands_at_impact"].status == "warn"


def test_left_hander_mirrored_gives_same_results():
    args = dict(hands_dx=-0.15 * TORSO, hip_dx=0.3 * TORSO, head_dx=-0.2 * TORSO)
    right = run_fo(face_on_pose(**args))
    left = run_fo(face_on_pose(**args, mirror=True), mirror=True)
    for name in right:
        assert left[name].label == right[name].label, name
        for key, value in right[name].measurements.items():
            if isinstance(value, float):
                assert left[name].measurements[key] == pytest.approx(value, abs=1e-3), (name, key)


def test_thresholds_come_from_config():
    config = copy.deepcopy(CONFIG)
    config["analyzers"]["weight_shift"]["min_shift"] = 0.5
    v = run_fo(face_on_pose(hip_dx=0.25 * TORSO), config=config)
    assert v["weight_shift"].status == "flag"


def test_disabled_analyzer_skipped():
    config = copy.deepcopy(CONFIG)
    config["analyzers"]["disabled"] = ["head_drift"]
    assert "head_drift" not in run_fo(face_on_pose(), config=config)


def test_missing_keypoints_give_error_verdict_not_crash():
    pose = face_on_pose()
    pose.data[:, LANDMARK_INDEX["left_hip"]] = np.nan
    v = run_fo(pose)
    assert v["weight_shift"].status == "error"
    assert v["hands_at_impact"].status != "error"


def test_new_analyzer_plugs_in_without_pipeline_changes():
    @register("test_only_dummy", view="fo", title="Dummy")
    def dummy(ctx):
        raise RuntimeError("boom")

    try:
        v = run_fo(face_on_pose())
        assert v["test_only_dummy"].status == "error"  # a crash is contained
        assert v["weight_shift"].status in ("ok", "flag")
    finally:
        REGISTRY.pop("test_only_dummy")


def test_register_rejects_bad_view():
    with pytest.raises(ValueError):
        register("x", view="side", title="x")


def test_verdict_json_has_no_overlays():
    d = Verdict(status="ok", label="x", summary="y").to_json()
    assert "overlays" not in d
    assert analyzers.STATUSES[0] == "ok"
