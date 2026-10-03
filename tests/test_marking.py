import numpy as np

from swingcheck.config import load_config
from swingcheck.ingest import VideoInfo
from swingcheck.marking import MarkSession, _render, display_limits, display_scale
from swingcheck.pipeline import load_marks, video_signature
from swingcheck.models import Marks


def make_info(**overrides) -> VideoInfo:
    fields = dict(
        source="x.mov", source_size=1, source_mtime=0.0, trim_start=None, trim_end=None,
        fps=240.0, width=1080, height=1920, rotation=90, frame_count=480, duration=2.0,
        source_codec="hevc", hdr=False, warnings=[],
    )
    fields.update(overrides)
    return VideoInfo(**fields)


def test_session_dtl_click_order_and_undo():
    s = MarkSession(view="dtl", frame_count=100)
    assert s.next_mark == "ball"
    s.click((10, 20))
    s.click((30, 40))
    assert s.next_mark == "grip"
    s.undo()
    assert s.next_mark == "clubhead"
    s.click((30, 41))
    s.click((50, 60))
    assert s.complete
    s.click((0, 0))  # extra clicks are ignored once complete
    assert s.points == {"ball": (10, 20), "clubhead": (30, 41), "grip": (50, 60)}


def test_session_fo_needs_only_ball():
    s = MarkSession(view="fo", frame_count=10)
    s.click((1, 2))
    assert s.complete


def test_step_clamps():
    s = MarkSession(view="fo", frame_count=10, frame=5)
    s.step(-10)
    assert s.frame == 0
    s.step(100)
    assert s.frame == 9


def test_display_scale_fits_tall_video():
    scale = display_scale(1080, 1920, 1600, 900)
    assert abs(1920 * scale - 900) < 1e-6
    assert display_scale(640, 480, 1600, 900) == 1.0  # never upscale


def test_display_limits_fit_screen():
    cfg = {"screen_fraction": 0.85, "max_display_width": 0, "max_display_height": 0}
    w, h = display_limits(cfg, work_area=(1920, 1040))
    assert (w, h) == (1632, 844)
    # Portrait video then fits the height of a 1080p laptop screen.
    assert 1920 * display_scale(1080, 1920, w, h) <= 844
    # Config caps still apply on top of the screen fit.
    w, h = display_limits({**cfg, "max_display_height": 600}, work_area=(1920, 1040))
    assert h == 600


def test_saved_marks_reused_only_when_video_matches(tmp_path):
    info = make_info()
    path = tmp_path / "marks.json"
    Marks(view="fo", address_frame=3, points={"ball": (5.0, 6.0)}, video_signature=video_signature(info)).save(path)

    assert load_marks(path, "fo", info).points["ball"] == (5.0, 6.0)
    assert load_marks(path, "dtl", info) is None  # wrong view
    assert load_marks(path, "fo", make_info(trim_start=1.0)) is None  # re-trimmed video


def test_render_headless_smoke():
    config = load_config()
    frame = np.zeros((1920, 1080, 3), dtype=np.uint8)
    s = MarkSession(view="dtl", frame_count=10, points={"ball": (500.0, 1800.0)})
    scale = display_scale(1080, 1920, 1600, 900)
    for cursor in [(0.0, 0.0), (1079.0, 1919.0), (2000.0, -5.0), None]:
        canvas = _render(s, frame, scale, cursor, config["marking"])
        assert canvas.shape[0] == 900
