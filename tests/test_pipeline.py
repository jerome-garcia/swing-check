import pytest

from swingcheck.config import load_config
from swingcheck.pipeline import PipelineError, analyze, load_marks, save_marks
from tests.test_marking import make_info

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
