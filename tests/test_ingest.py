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


def test_choose_fps_keeps_timeline_rate_when_frames_are_missing():
    # Shared iPhone slo-mo: a 59.94 fps timeline with gaps, averaging 41.7.
    fps, warnings = choose_fps({"avg_frame_rate": "750000/17969", "r_frame_rate": "60000/1001"})
    assert fps == 60
    assert "missing" in warnings[0]
    # A real 29.97 clip averaging a hair under its timeline rate is not gappy.
    assert choose_fps({"avg_frame_rate": "2997/101", "r_frame_rate": "30000/1001"}) == (30, [])


def test_choose_fps_falls_back_when_missing():
    fps, warnings = choose_fps({"avg_frame_rate": "0/0", "r_frame_rate": "0/0"})
    assert fps == FALLBACK_FPS
    assert warnings


def test_parse_rotation():
    assert parse_rotation({"side_data_list": [{"rotation": -90}]}) == 270
    assert parse_rotation({"tags": {"rotate": "90"}}) == 90
    assert parse_rotation({}) == 0
    assert parse_rotation({"tags": {"rotate": "junk"}}) == 0
