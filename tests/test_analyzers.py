import copy

import numpy as np
import pytest

from swingcheck import analyzers
from swingcheck.analyzers import REGISTRY, SwingContext, Verdict, analyzers_for, register, run_analyzers
from swingcheck.config import for_club, load_config
from swingcheck.models import LANDMARK_INDEX, LANDMARKS, CheckpointMark, Marks, PoseSeq
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
    # Facing the camera, a right-hander's left (front) side is on screen-right, the target side.
    base = {
        "nose": (540, 300), "left_ear": (555, 290), "right_ear": (525, 290),
        "left_shoulder": (600, 400), "right_shoulder": (480, 400),
        "left_hip": (580, 660), "right_hip": (500, 660),
        "left_wrist": (535, 760), "right_wrist": (545, 760),
        # Feet 1.33x shoulder width, the front (left) one on the target side, screen-right.
        "left_ankle": (620, 1000), "right_ankle": (460, 1000),
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
                     ("left_shoulder", "right_shoulder"), ("left_ankle", "right_ankle")]:
            ia, ib = LANDMARK_INDEX[a], LANDMARK_INDEX[b]
            data[:, [ia, ib]] = data[:, [ib, ia]]
    return PoseSeq(fps=240.0, width=width, height=1920, data=data)


def run_fo(pose, mirror=False, config=None, hands_dx=0.1 * TORSO, club="iron", clicked=True):
    """Face-on analyzers on a made-up swing. The hands are clicked on the impact frame
    `hands_dx` px toward screen-right of the ball (the target side for a right-hander)."""
    config = copy.deepcopy(config or CONFIG)
    if club != "iron":
        config = for_club(config, club)
    config["pose"]["smoothing_ms"] = 0  # keep the step change crisp
    if mirror:
        config["golfer"]["handedness"] = "left"
    flip = (lambda x: 1080 - 1 - x) if mirror else (lambda x: x)
    # The made-up swing moves only at impact (frame 80), so downswing and finish are marked
    # just after it, where the shift shows.
    frames = {"top": CheckpointMark(frame=PHASES.top, points={}), "downswing": CheckpointMark(frame=82, points={}),
              "finish": CheckpointMark(frame=95, points={})}
    if clicked:
        frames["impact"] = CheckpointMark(frame=PHASES.impact, points={"grip": (flip(BALL_X + hands_dx), 760.0)})
    marks = Marks(view="fo", address_frame=10, points={"ball": (flip(BALL_X), 1000.0)}, checkpoints=frames)
    ctx = SwingContext(view="fo", pose=pose, marks=marks, phases=PHASES, scale=TORSO, config=config)
    return {v.name: v for v in run_analyzers(ctx)}


def test_builtin_fo_analyzers_registered():
    assert "fo_impact" in {a.name for a in analyzers_for("fo", CONFIG)}
    assert all(a.view == "fo" for a in analyzers_for("fo", CONFIG))


def test_good_impact_is_green():
    # Right-hander, target screen-right: hands ahead, hips forward, head behind the ball.
    v = run_fo(face_on_pose(hip_dx=0.25 * TORSO, head_dx=-0.1 * TORSO))["fo_impact"]
    assert v.status == "ok" and v.label == "Hands ahead, hips forward, head behind the ball"
    assert [r.status for r in v.rows] == ["ok", "ok", "ok"]


def test_scoop_and_hanging_back_are_red():
    v = run_fo(face_on_pose(hip_dx=-0.05 * TORSO, head_dx=-0.1 * TORSO), hands_dx=-0.15 * TORSO)["fo_impact"]
    assert v.status == "flag" and v.label == "Hands behind the ball"
    assert [r.status for r in v.rows] == ["flag", "flag", "ok"]
    assert v.measurements["hands_ahead_of_ball"] == pytest.approx(-0.15, abs=1e-3)
    assert "Lead with your hands" in v.tip and "front foot" in v.tip


def test_hands_level_with_the_ball_are_yellow():
    v = run_fo(face_on_pose(hip_dx=0.25 * TORSO, head_dx=-0.1 * TORSO), hands_dx=0.0)["fo_impact"]
    assert v.status == "warn" and v.label == "Hands about level with the ball"


def test_head_past_the_ball_is_red_and_far_behind_only_yellow():
    lunge = run_fo(face_on_pose(hip_dx=0.25 * TORSO, head_dx=0.2 * TORSO))["fo_impact"]
    assert lunge.status == "flag" and lunge.label == "Head past the ball"
    back = run_fo(face_on_pose(hip_dx=0.25 * TORSO, head_dx=-0.9 * TORSO))["fo_impact"]
    assert back.status == "warn" and back.label == "Head well behind the ball"


def test_driver_hands_behind_the_ball_are_a_watch_item():
    good = run_fo(face_on_pose(hip_dx=0.25 * TORSO, head_dx=-0.1 * TORSO), hands_dx=-0.15 * TORSO, club="driver")
    assert good["fo_impact"].status == "ok"
    far = run_fo(face_on_pose(hip_dx=0.25 * TORSO, head_dx=-0.1 * TORSO), hands_dx=-0.6 * TORSO, club="driver")
    assert far["fo_impact"].status == "warn" and far["fo_impact"].rows[0].fix == "none (a watch item only)"


def test_hands_not_clicked_says_how_to_fix():
    v = run_fo(face_on_pose(), clicked=False)["fo_impact"]
    assert v.status == "error" and "Impact step" in v.summary


def test_left_hander_mirrored_gives_same_results():
    args = dict(hip_dx=0.3 * TORSO, head_dx=-0.2 * TORSO)
    right = run_fo(face_on_pose(**args), hands_dx=-0.15 * TORSO)["fo_impact"]
    left = run_fo(face_on_pose(**args, mirror=True), mirror=True, hands_dx=-0.15 * TORSO)["fo_impact"]
    assert left.label == right.label
    for key, value in right.measurements.items():
        if isinstance(value, float):
            assert left.measurements[key] == pytest.approx(value, abs=1e-3), key


def test_thresholds_come_from_config():
    config = copy.deepcopy(CONFIG)
    config["analyzers"]["fo_impact"]["hips_shift_min"] = 0.5
    v = run_fo(face_on_pose(hip_dx=0.25 * TORSO, head_dx=-0.1 * TORSO), config=config)["fo_impact"]
    assert v.rows[1].status == "warn"


def test_disabled_analyzer_skipped():
    config = copy.deepcopy(CONFIG)
    config["analyzers"]["disabled"] = ["fo_impact"]
    assert "fo_impact" not in run_fo(face_on_pose(), config=config)


def test_missing_keypoints_give_error_verdict_not_crash():
    pose = face_on_pose()
    pose.data[:, LANDMARK_INDEX["left_hip"]] = np.nan
    assert run_fo(pose)["fo_impact"].status == "error"


def moved(pose, name, dx):
    """The pose with one body point moved dx px along x on every frame."""
    pose.data[:, LANDMARK_INDEX[name], 0] += dx
    return pose


def test_good_address_from_the_front_is_green():
    v = run_fo(face_on_pose())["fo_address"]
    assert v.status == "ok" and v.label == "Good setup from the front"
    m = v.measurements
    assert m["stance_over_shoulders"] == pytest.approx(160 / 120, abs=1e-3) and m["ball_position"] == pytest.approx(0.5)
    assert m["spine_tilt_deg"] == pytest.approx(0.0)


def test_address_faults_are_named():
    narrow = moved(moved(face_on_pose(), "left_ankle", -45), "right_ankle", 45)  # 0.58x shoulder width
    assert run_fo(narrow)["fo_address"].label == "Stance too narrow"
    back = moved(moved(face_on_pose(), "left_ankle", 120), "right_ankle", 120)  # ball behind the back ankle
    assert run_fo(back)["fo_address"].label == "Ball too far back"
    lean = moved(moved(face_on_pose(), "left_shoulder", 50), "right_shoulder", 50)  # 11 deg toward the target
    v = run_fo(lean)["fo_address"]
    assert v.status == "flag" and v.label == "Leaning toward the target" and "back shoulder" in v.tip


def test_driver_address_wants_a_wider_stance_and_the_ball_forward():
    v = run_fo(face_on_pose(), club="driver")["fo_address"]  # 1.33x, ball in the middle
    assert [r.status for r in v.rows] == ["ok", "warn", "ok"] and v.label == "Ball slightly back"


def test_left_hander_address_matches():
    lean = dict(dx=30)
    right = run_fo(moved(moved(face_on_pose(), "left_shoulder", lean["dx"]), "right_shoulder", lean["dx"]))
    left = run_fo(moved(moved(face_on_pose(mirror=True), "left_shoulder", -lean["dx"]), "right_shoulder", -lean["dx"]),
                  mirror=True)
    for key in ("stance_over_shoulders", "ball_position", "spine_tilt_deg"):
        assert left["fo_address"].measurements[key] == pytest.approx(right["fo_address"].measurements[key], abs=1e-3)


def shifted(pose, names, frame, dx):
    """The pose with these body points moved dx px along x from `frame` on."""
    for name in names:
        pose.data[frame:, LANDMARK_INDEX[name], 0] += dx
    return pose


HEAD = ("nose", "left_ear", "right_ear")


def test_top_sway_and_head_movement():
    good = run_fo(face_on_pose())["fo_top"]  # back hip 6 cm inside the back ankle, head still
    assert good.status == "ok" and good.label == "No sway, head steady"
    sway = run_fo(shifted(face_on_pose(), ["right_hip"], PHASES.top, -60))["fo_top"]  # back hip out past the ankle
    assert sway.status == "flag" and sway.label == "Swaying" and "Turn your hips" in sway.tip
    reverse = run_fo(shifted(face_on_pose(), HEAD, PHASES.top, 0.15 * TORSO))["fo_top"]  # head toward the target
    assert reverse.status == "flag" and reverse.label == "Head toward the target"


def test_downswing_hips_lead_and_head_stays_back():
    good = run_fo(face_on_pose(hip_dx=0.25 * TORSO))["fo_downswing"]
    assert good.status == "ok" and good.label == "Hips leading, head back"
    stuck = run_fo(face_on_pose(hip_dx=0.02 * TORSO))["fo_downswing"]
    assert stuck.status == "flag" and stuck.label == "Hips not moving"
    lunge = run_fo(face_on_pose(hip_dx=0.25 * TORSO, head_dx=0.3 * TORSO))["fo_downswing"]
    assert lunge.status == "flag" and lunge.label == "Head lunging forward"


def test_finish_on_the_front_side():
    good = run_fo(face_on_pose(hip_dx=0.25 * TORSO))["fo_finish"]
    assert good.status == "ok" and good.label == "Balanced on the front side"
    # Downswing and finish have no detected phase: their key frames are the marked frames.
    v = run_fo(face_on_pose(hip_dx=0.25 * TORSO))
    assert (v["fo_downswing"].frame, v["fo_finish"].frame) == (82, 95)
    back = run_fo(face_on_pose(hip_dx=-0.05 * TORSO))["fo_finish"]
    assert back.status == "warn" and back.label == "Finishing on the back foot"  # never red: the ball is gone
    # Tracking lost on the finish frame itself: the frame just before stands in.
    pose = face_on_pose(hip_dx=0.25 * TORSO)
    pose.data[95:, :, :] = np.nan
    assert run_fo(pose)["fo_finish"].status == "ok"


def test_new_analyzer_plugs_in_without_pipeline_changes():
    @register("test_only_dummy", view="fo", title="Dummy")
    def dummy(ctx):
        raise RuntimeError("boom")

    try:
        v = run_fo(face_on_pose())
        assert v["test_only_dummy"].status == "error"  # a crash is contained
        assert v["fo_impact"].status in ("ok", "warn", "flag")
    finally:
        REGISTRY.pop("test_only_dummy")


def test_register_rejects_bad_view():
    with pytest.raises(ValueError):
        register("x", view="side", title="x")


def test_verdict_json_has_no_overlays():
    d = Verdict(status="ok", label="x", summary="y").to_json()
    assert "overlays" not in d
    assert analyzers.STATUSES[0] == "ok"
