import numpy as np
import pytest

from swingcheck.config import load_config
from swingcheck.phases import PhaseError, Phases, apply_overrides, detect_phases

CFG = load_config()["phases"]
SCALE = 260.0  # torso length in px


def synthetic_swing(fps: float, seed: int = 0, waggle: bool = False, noise: float = 0.5, creep: bool = False):
    """Hand track (frames, 2) for a stylized swing, plus the true phase frames.

    still address -> backswing up -> short pause at top -> accelerating
    downswing -> impact -> follow-through to a finish higher than the top.
    """
    rng = np.random.default_rng(seed)
    segments = []
    truth = {}

    def add(n_s, xs, ys):
        n = int(round(n_s * fps))
        s = np.linspace(0, 1, n, endpoint=False)
        segments.append(np.stack([xs(s), ys(s)], axis=1))
        return sum(len(seg) for seg in segments)

    if waggle:
        add(0.4, lambda s: 300 + 12 * np.sin(2 * np.pi * s), lambda s: 800 - 8 * np.sin(2 * np.pi * s) ** 2)
    end_still = add(0.6, lambda s: 300 + 0 * s, lambda s: 800 + 0 * s)
    truth["address"] = end_still - 1
    if creep:  # a takeaway that starts too slowly to count as moving: 8 px over 0.3 s
        add(0.3, lambda s: 300 - 8 * s, lambda s: 800 + 0 * s)
    ease = lambda s: (1 - np.cos(np.pi * s)) / 2  # noqa: E731
    x0 = 292 if creep else 300
    end_back = add(0.8, lambda s: x0 - 100 * np.sin(np.pi * s), lambda s: 800 - 420 * ease(s))
    end_pause = add(0.1, lambda s: 300 + 0 * s, lambda s: 380 + 0 * s)
    truth["top"] = (end_back + end_pause) // 2
    end_down = add(0.25, lambda s: 300 + 40 * s, lambda s: 380 + 410 * s**2)
    truth["impact"] = end_down
    add(0.5, lambda s: 340 + 80 * s, lambda s: 790 - 490 * np.sin(np.pi / 2 * s))
    add(0.3, lambda s: 420 + 0 * s, lambda s: 300 + 0 * s)

    track = np.concatenate(segments)
    track += rng.normal(0, noise, track.shape)
    return track, truth


def assert_address(phases: Phases, truth: dict, fps: float):
    """Address lands on the still set-up: never after it ends, and at most ~150 ms before."""
    assert truth["address"] - max(2, 0.15 * fps) <= phases.address <= truth["address"],         f"address: got {phases.address}, want up to {truth['address']} (fps {fps})"


def assert_close(phases: Phases, truth: dict, fps: float, tol_ms: dict):
    for name, ms in tol_ms.items():
        got, want = getattr(phases, name), truth[name]
        assert abs(got - want) <= max(1, ms * fps / 1000), f"{name}: got {got}, want {want} (fps {fps})"


@pytest.mark.parametrize("fps", [30.0, 60.0, 240.0])
def test_detects_phases_at_common_frame_rates(fps):
    track, truth = synthetic_swing(fps)
    phases = detect_phases(track, fps, SCALE, CFG)
    assert_close(phases, truth, fps, {"top": 60, "impact": 15})
    assert_address(phases, truth, fps)
    assert phases.address < phases.takeaway < phases.top < phases.early_downswing < phases.impact


def test_waggle_before_address_is_ignored():
    fps = 240.0
    track, truth = synthetic_swing(fps, waggle=True)
    phases = detect_phases(track, fps, SCALE, CFG)
    assert_close(phases, truth, fps, {"top": 60, "impact": 15})
    assert_address(phases, truth, fps)


@pytest.mark.parametrize("fps", [30.0, 240.0])
def test_slow_start_of_the_takeaway_is_not_address(fps):
    track, truth = synthetic_swing(fps, creep=True)
    assert_address(detect_phases(track, fps, SCALE, CFG), truth, fps)


def test_finish_higher_than_top_is_not_mistaken_for_top():
    fps = 240.0
    track, truth = synthetic_swing(fps)
    assert track[:, 1].min() < track[truth["top"], 1]  # finish really is higher
    phases = detect_phases(track, fps, SCALE, CFG)
    assert phases.top < phases.impact
    assert_close(phases, truth, fps, {"top": 60})


def test_tracking_gap_at_impact():
    fps = 240.0
    track, truth = synthetic_swing(fps)
    gap = slice(truth["impact"] - 3, truth["impact"] + 3)  # 25 ms of lost hands (motion blur)
    track[gap] = np.nan
    from swingcheck.pose import clean_track

    filled = clean_track(track, fps, max_gap_ms=100, smoothing_ms=0)
    phases = detect_phases(filled, fps, SCALE, CFG)
    assert_close(phases, truth, fps, {"impact": 20})


def test_tracker_seam_outside_search_window_is_ignored():
    # A pass boundary early in the clip makes the hands jump down 150 px in one frame,
    # faster than the real downswing. Limiting the search to the swing's stretch ignores it.
    fps = 240.0
    track, truth = synthetic_swing(fps)
    track[20:, 1] += 150
    track[40:, 1] -= 150
    try:
        fooled = detect_phases(track, fps, SCALE, CFG)
        assert fooled.impact < 60  # without a search window the seam wins
    except PhaseError:
        pass  # or detection gives up entirely
    phases = detect_phases(track, fps, SCALE, CFG, search=(60, len(track) - 1))
    assert_close(phases, truth, fps, {"top": 60, "impact": 15})


def test_scale_invariant():
    fps = 240.0
    track, _ = synthetic_swing(fps, noise=0.0)
    a = detect_phases(track, fps, SCALE, CFG)
    b = detect_phases(track * 2, fps, SCALE * 2, CFG)
    assert a.as_dict() == b.as_dict()


def test_tracking_wobble_mid_downswing_doesnt_stop_impact_search():
    # Blurry footage: fast drop, the hands bounce back up a little for a frame,
    # then keep coming down more slowly to impact (seen on a real 60 fps clip).
    fps = 60.0
    keys = [(0, 800), (40, 800), (80, 380), (85, 380), (93, 700), (96, 685), (110, 790), (140, 300), (160, 300)]
    frames = np.arange(161)
    y = np.interp(frames, [k for k, _ in keys], [v for _, v in keys])
    track = np.stack([np.full_like(y, 300.0), y], axis=1)
    phases = detect_phases(track, fps, SCALE, CFG)
    assert abs(phases.impact - 110) <= 1


def test_flat_track_raises():
    track = np.full((200, 2), 500.0)
    with pytest.raises(PhaseError):
        detect_phases(track, 240.0, SCALE, CFG)


def test_override_recomputes_checkpoints():
    fps = 240.0
    track, _ = synthetic_swing(fps)
    auto = detect_phases(track, fps, SCALE, CFG)
    moved = apply_overrides(auto, {"top": auto.top - 20}, track, fps, CFG, len(track))
    assert moved.top == auto.top - 20
    assert moved.manual == ["top"]
    assert moved.address == auto.address and moved.impact == auto.impact
    assert moved.takeaway <= moved.top <= moved.early_downswing


def test_overrides_required_when_detection_failed():
    track = np.full((200, 2), 500.0)
    with pytest.raises(PhaseError, match="--top"):
        apply_overrides(None, {"address": 10, "impact": 150}, track, 240.0, CFG, 200)
    phases = apply_overrides(None, {"address": 10, "top": 80, "impact": 150}, track, 240.0, CFG, 200)
    assert phases.manual == ["address", "top", "impact"]


def test_bad_override_order_rejected():
    fps = 240.0
    track, _ = synthetic_swing(fps)
    auto = detect_phases(track, fps, SCALE, CFG)
    with pytest.raises(PhaseError, match="The top frame you set .* comes after the impact"):
        apply_overrides(auto, {"top": auto.impact + 5}, track, fps, CFG, len(track))


def test_impact_set_before_top_is_a_plain_error():
    # The golfer's frame stays theirs: no guessing a different top, just say what's wrong.
    from swingcheck.phases import PhaseOrderError

    fps = 240.0
    track, _ = synthetic_swing(fps)
    auto = detect_phases(track, fps, SCALE, CFG)
    with pytest.raises(PhaseOrderError) as e:
        apply_overrides(auto, {"impact": auto.top - 3}, track, fps, CFG, len(track))
    assert str(e.value) == (f"The impact frame you set ({auto.top - 3}) comes before the top (frame {auto.top}). "
                            "Pick an impact frame after the top, or reset it to automatic.")


def test_marked_takeaway_replaces_detected_one(tmp_path):
    from swingcheck.phases import get_phases

    fps = 240.0
    track, truth = synthetic_swing(fps)
    config = {"phases": CFG}
    auto, _ = get_phases(tmp_path, track, fps, SCALE, config, {}, {})
    mark = (auto.address + auto.top) // 2 + 7
    phases, _ = get_phases(tmp_path, track, fps, SCALE, config, {}, {}, marked_takeaway=mark)
    assert phases.takeaway == mark and "takeaway" in phases.manual
    # A marked frame outside address..top is ignored.
    phases, _ = get_phases(tmp_path, track, fps, SCALE, config, {}, {}, marked_takeaway=auto.impact)
    assert phases.takeaway == auto.takeaway and "takeaway" not in phases.manual


def test_takeaway_counts_hands_moving_back_not_just_up():
    # Down the line, the hands first move back (sideways on screen) and only then rise.
    from swingcheck.phases import checkpoints
    back = np.stack([np.linspace(300, 220, 11), np.full(11, 800.0)], axis=1)   # 80 px back, flat
    up = np.stack([np.full(30, 220.0), np.linspace(800, 500, 31)[1:]], axis=1)  # then 300 px up
    xy = np.concatenate([back, up, np.tile([[220.0, 790.0]], (5, 1))])
    takeaway, _ = checkpoints(xy, address=0, top=40, impact=45, takeaway_fraction=0.12, downswing_fraction=0.35)
    assert takeaway == 6  # 12% of the 380 px path, while still moving back; height alone would wait until it rose


def test_halfway_back_is_where_the_hands_are_partway_up():
    from swingcheck.phases import halfway_back
    fps = 240.0
    track, truth = synthetic_swing(fps)
    phases = detect_phases(track, fps, SCALE, CFG)
    frame = halfway_back(track, fps, phases, CFG)
    assert phases.takeaway < frame < phases.top
    y = track[:, 1]
    risen = (y[phases.address] - y[frame]) / (y[phases.address] - y[phases.top])
    assert abs(risen - CFG["halfway_back_fraction"]) < 0.05
