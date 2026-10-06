import pytest

from swingcheck.config import load_config
from swingcheck.pipeline import PipelineError, analyze, load_marks, save_marks
from tests.helpers import make_info

CONFIG = load_config()


def test_save_marks_requires_all_points_for_view(tmp_path):
    info = make_info()
    with pytest.raises(PipelineError, match="clubhead"):
        save_marks(tmp_path, "dtl", 10, {"ball": (1, 2), "grip": (3, 4)}, info)
    marks = save_marks(tmp_path, "fo", 10, {"ball": (1, 2), "grip": (3, 4)}, info)
    assert marks.points == {"ball": (1.0, 2.0)}  # extra points for other views are dropped
    assert load_marks(tmp_path / "marks.json", "fo", info).address_frame == 10


def test_save_marks_rejects_frame_outside_clip(tmp_path):
    with pytest.raises(PipelineError, match="outside"):
        save_marks(tmp_path, "fo", 10_000, {"ball": (1, 2)}, make_info())


def test_save_marks_rejects_checkpoints_out_of_order(tmp_path):
    address = {"ball": (1, 2), "clubhead": (3, 4), "grip": (5, 6)}
    cps = {"takeaway": {"frame": 30, "points": {"clubhead": (1, 1)}},
           "halfway_back": {"frame": 25, "points": {"clubhead": (1, 1), "grip": (2, 2)}}}
    with pytest.raises(PipelineError, match="Your halfway back frame comes before your takeaway frame"):
        save_marks(tmp_path, "dtl", 10, address, make_info(), checkpoints=cps)
    cps["halfway_back"]["frame"] = 40
    assert save_marks(tmp_path, "dtl", 10, address, make_info(), checkpoints=cps).checkpoint("halfway_back").frame == 40


def test_analyze_needs_converted_video(tmp_path):
    with pytest.raises(PipelineError, match="converted"):
        analyze(tmp_path, "dtl", CONFIG)


def test_analyze_needs_marks(tmp_path):
    make_info().save(tmp_path / "video.json")
    with pytest.raises(PipelineError, match="Mark"):
        analyze(tmp_path, "dtl", CONFIG)


def test_saved_marks_reused_only_when_video_matches(tmp_path):
    info = make_info()
    save_marks(tmp_path, "fo", 3, {"ball": (5.0, 6.0)}, info)
    path = tmp_path / "marks.json"
    assert load_marks(path, "fo", info).points["ball"] == (5.0, 6.0)
    assert load_marks(path, "dtl", info) is None  # wrong view
    assert load_marks(path, "fo", make_info(trim_start=1.0)) is None  # re-trimmed video


def test_takeaway_marks_saved_and_validated(tmp_path):
    info = make_info()
    address = {"ball": (1, 2), "clubhead": (3, 4), "grip": (5, 6)}
    marks = save_marks(tmp_path, "dtl", 10, address, info,
                       checkpoints={"takeaway": {"frame": 60, "points": {"clubhead": (7, 8), "grip": (9, 10), "x": (0, 0)}}})
    loaded = load_marks(tmp_path / "marks.json", "dtl", info)
    assert loaded.checkpoint("takeaway").frame == 60
    assert loaded.checkpoint("takeaway").points == {"clubhead": (7.0, 8.0)}  # a hands click is no longer kept
    # Partly marked (the top takes clubhead and hands): kept in the file, but doesn't
    # count as a usable checkpoint.
    save_marks(tmp_path, "dtl", 10, address, info, checkpoints={"top": {"frame": 60, "points": {"clubhead": (7, 8)}}})
    assert load_marks(tmp_path / "marks.json", "dtl", info).checkpoint("top") is None
    # Nothing clicked: dropped. Old marks files without checkpoints still load.
    save_marks(tmp_path, "dtl", 10, address, info, checkpoints={"takeaway": {"frame": 60, "points": {}}})
    assert load_marks(tmp_path / "marks.json", "dtl", info).checkpoints == {}
    with pytest.raises(PipelineError, match="after the address"):
        save_marks(tmp_path, "dtl", 10, address, info, checkpoints={"takeaway": {"frame": 5, "points": {"clubhead": (1, 1)}}})
    with pytest.raises(PipelineError, match="Unknown"):
        save_marks(tmp_path, "dtl", 10, address, info, checkpoints={"finish": {"frame": 50, "points": {"clubhead": (1, 1)}}})
    assert marks.view == "dtl"


def test_suggest_frames_saves_detected_phases_for_this_video(tmp_path, monkeypatch):
    import numpy as np

    from swingcheck import pipeline
    from swingcheck.phases import Phases

    info = make_info(frame_count=480)
    calls = {}

    def fake_extract(video, info_, config, select=None, **kw):
        calls["sampled"] = [i for i in range(16) if select(i)]
        return np.full((info_.frame_count, 33, 4), np.nan)

    monkeypatch.setattr(pipeline, "extract_pose", fake_extract)
    monkeypatch.setattr(pipeline, "detect_phases",
                        lambda *a, **k: Phases(address=10, takeaway=40, top=200, early_downswing=260, impact=300))
    frames = pipeline.suggest_frames(tmp_path, info, load_config())
    # halfway back: no hands in the fake pose, so halfway from takeaway to top
    assert frames == {"address": 10, "takeaway": 40, "top": 200, "early_downswing": 260, "impact": 300, "halfway_back": 120}
    assert calls["sampled"] == [0, 8]  # 240 fps clip, quick pass at 30 fps
    assert pipeline.load_suggested(tmp_path, info) == frames
    assert pipeline.load_suggested(tmp_path, make_info(frame_count=200)) is None  # re-trimmed: stale
    assert pipeline.load_camera_check(tmp_path, info)[0]["title"] == "No golfer found"  # the fake pose is empty


def test_suggest_frames_gives_up_quietly_when_no_swing_found(tmp_path, monkeypatch):
    import numpy as np

    from swingcheck import pipeline

    info = make_info()
    (tmp_path / pipeline.SUGGEST_FILE).write_text('{"phases": {"top": 1}}')  # left over from an earlier conversion
    monkeypatch.setattr(pipeline, "extract_pose", lambda video, i, c, **kw: np.full((i.frame_count, 33, 4), np.nan))
    assert pipeline.suggest_frames(tmp_path, info, load_config()) is None
    assert pipeline.load_suggested(tmp_path, info) is None
    # The camera check still says what went wrong.
    assert [f["title"] for f in pipeline.load_camera_check(tmp_path, info)] == ["No golfer found"]
