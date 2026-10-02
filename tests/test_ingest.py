from swingcheck.ingest import FALLBACK_FPS, choose_fps, parse_rate, parse_rotation, snap_fps


def test_parse_rate():
    assert abs(parse_rate("30000/1001") - 29.97) < 0.01
    assert parse_rate("0/0") is None
    assert parse_rate("") is None
    assert parse_rate(None) is None


def test_snap_fps():
    assert snap_fps(239.7) == 240
    assert snap_fps(29.97) == 30
    assert snap_fps(59.94) == 60
    assert snap_fps(87.0) == 87.0  # nothing standard nearby: keep it


def test_choose_fps_prefers_average_for_vfr():
    # iPhone VFR: r_frame_rate can be a huge timebase-like value.
    fps, warnings = choose_fps({"avg_frame_rate": "14385/60", "r_frame_rate": "600/1"})
    assert fps == 240
    assert warnings == []


def test_choose_fps_falls_back_when_missing():
    fps, warnings = choose_fps({"avg_frame_rate": "0/0", "r_frame_rate": "0/0"})
    assert fps == FALLBACK_FPS
    assert warnings


def test_parse_rotation():
    assert parse_rotation({"side_data_list": [{"rotation": -90}]}) == 270
    assert parse_rotation({"tags": {"rotate": "90"}}) == 90
    assert parse_rotation({}) == 0
    assert parse_rotation({"tags": {"rotate": "junk"}}) == 0
