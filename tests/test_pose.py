import numpy as np

from swingcheck.models import LANDMARKS, PoseSeq
from swingcheck.pose import clean_track, load_pose, save_pose


def test_short_gap_filled_long_gap_kept():
    fps = 100.0
    x = np.arange(20, dtype=float)
    x[5:8] = np.nan      # 30 ms gap -> filled
    x[10:18] = np.nan    # 80 ms gap -> too long at max_gap 50 ms
    out = clean_track(np.stack([x, x], axis=1), fps, max_gap_ms=50, smoothing_ms=0)
    assert np.allclose(out[5:8, 0], [5, 6, 7])
    assert np.isnan(out[10:18, 0]).all()


def test_leading_and_trailing_gaps_not_extrapolated():
    x = np.array([np.nan, 1.0, 2.0, np.nan])
    out = clean_track(x[:, None], fps=100, max_gap_ms=1000, smoothing_ms=0)
    assert np.isnan(out[0, 0]) and np.isnan(out[3, 0])


def test_smoothing_keeps_linear_motion_and_damps_noise():
    fps = 240.0
    t = np.arange(100, dtype=float)
    noisy = t.copy()
    noisy[50] += 10
    out = clean_track(noisy[:, None], fps, max_gap_ms=0, smoothing_ms=25)
    assert abs(out[30, 0] - 30) < 1e-9  # straight line passes through unchanged
    assert abs(out[50, 0] - 50) < 10 / 3  # spike spread over the window


def test_pose_cache_roundtrip(tmp_path):
    data = np.full((3, len(LANDMARKS), 4), np.nan)
    data[0] = np.random.default_rng(0).random((len(LANDMARKS), 4)) * 100
    data[2] = 1.0
    pose = PoseSeq(fps=240.0, width=1080, height=1920, data=data)
    save_pose(tmp_path / "pose.json", pose, {"model": "heavy"})
    loaded, params = load_pose(tmp_path / "pose.json")
    assert params == {"model": "heavy"}
    assert list(loaded.detected()) == [True, False, True]
    assert np.allclose(loaded.data[0, :, :2], data[0, :, :2], atol=0.01)
    assert loaded.xy("nose", min_visibility=2.0)[2].tolist() != loaded.xy("nose")[2].tolist()
