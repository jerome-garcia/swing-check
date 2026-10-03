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
    assert loaded.checkpoint("takeaway").points == {"clubhead": (7.0, 8.0), "grip": (9.0, 10.0)}
    # Partly marked: kept in the file, but doesn't count as a usable checkpoint.
    save_marks(tmp_path, "dtl", 10, address, info, checkpoints={"takeaway": {"frame": 60, "points": {"clubhead": (7, 8)}}})
    assert load_marks(tmp_path / "marks.json", "dtl", info).checkpoint("takeaway") is None
    # Nothing clicked: dropped. Old marks files without checkpoints still load.
    save_marks(tmp_path, "dtl", 10, address, info, checkpoints={"takeaway": {"frame": 60, "points": {}}})
    assert load_marks(tmp_path / "marks.json", "dtl", info).checkpoints == {}
    with pytest.raises(PipelineError, match="after the address"):
        save_marks(tmp_path, "dtl", 10, address, info, checkpoints={"takeaway": {"frame": 5, "points": {"clubhead": (1, 1)}}})
    with pytest.raises(PipelineError, match="Unknown"):
        save_marks(tmp_path, "dtl", 10, address, info, checkpoints={"top": {"frame": 50, "points": {"clubhead": (1, 1)}}})
    assert marks.view == "dtl"
