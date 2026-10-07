import shutil

import numpy as np
import pytest

from swingcheck.analyzers import Overlay, Verdict
from swingcheck.config import load_config
from swingcheck.ingest import VideoInfo
from swingcheck.output.annotate import Annotator, write_outputs
from swingcheck.output.report import build_report
from swingcheck.output.video import VideoWriter
from swingcheck.phases import Phases
from tests.test_analyzers import face_on_pose, run_fo

CONFIG = load_config()
PHASES = Phases(address=10, takeaway=30, top=50, early_downswing=70, impact=80)


def fo_verdicts():
    v = run_fo(face_on_pose(hands_dx=-40, hip_dx=10, head_dx=-50))
    return list(v.values())


def test_every_overlay_kind_renders():
    kinds = ["line", "ray", "segment", "point", "vline", "text", "circle", "square", "ring", "dashed"]
    overlays = [Overlay(k, [(100.0, 900.0), (300.0, 300.0)], label=k) for k in kinds]
    overlays.append(Overlay("point", [(50.0, 50.0)], thickness=1))  # ring marker
    overlays.append(Overlay("ray", [(-500.0, -500.0), (-400.0, -400.0)], label="off-frame"))  # misses frame
    verdict = Verdict(status="ok", label="x", summary="y", overlays=overlays, title="All kinds")
    hands = np.tile([540.0, 760.0], (100, 1))
    ann = Annotator([verdict], PHASES, hands, 240.0, 1080, 1920, CONFIG)
    frame = np.zeros((1920, 1080, 3), np.uint8)
    for i in (0, 10, 50, 80, 99):
        out = ann.render(frame, i, footer="footer")
        assert out.shape == frame.shape
    assert out.any()


def test_face_on_verdicts_render_through_impact():
    verdicts = fo_verdicts()
    assert {v.name for v in verdicts} == {"hands_at_impact", "weight_shift", "head_drift"}
    pose = face_on_pose()
    hands = (pose.xy("left_wrist") + pose.xy("right_wrist")) / 2
    ann = Annotator(verdicts, PHASES, hands, 240.0, 1080, 1920, CONFIG)
    frame = np.full((1920, 1080, 3), 90, np.uint8)
    before = ann.render(frame, 79)
    after = ann.render(frame, 80)
    assert not np.array_equal(before, after)  # impact-only overlays appear at impact


def test_hand_path_hidden_by_default():
    import copy

    hands = np.stack([np.linspace(300, 700, 100), np.linspace(1500, 500, 100)], axis=1)
    frame = np.zeros((1920, 1080, 3), np.uint8)
    off = Annotator([], PHASES, hands, 240.0, 1080, 1920, CONFIG).render(frame, 60)
    cfg = copy.deepcopy(CONFIG)
    cfg["output"]["show_hand_path"] = True
    on = Annotator([], PHASES, hands, 240.0, 1080, 1920, cfg).render(frame, 60)
    # The path runs through the middle of the frame, away from the labels at the edges.
    middle = (slice(900, 1300), slice(400, 600))
    assert not off[middle].any()
    assert on[middle].any()


def test_unknown_overlay_kind_rejected():
    verdict = Verdict(status="ok", label="x", summary="y", overlays=[Overlay("blob", [(0.0, 0.0)])])
    ann = Annotator([verdict], PHASES, np.zeros((100, 2)), 240.0, 100, 100, CONFIG)
    with pytest.raises(ValueError, match="blob"):
        ann.render(np.zeros((100, 100, 3), np.uint8), 5)


def test_report_lists_phases_and_flags():
    info = VideoInfo(source="x", source_size=1, source_mtime=0, trim_start=1.0, trim_end=None, fps=240.0,
                     width=1080, height=1920, rotation=90, frame_count=100, duration=0.4,
                     source_codec="hevc", hdr=False, warnings=["a note"])
    text = build_report(__import__("pathlib").Path("swing.mov"), "fo", info, PHASES, fo_verdicts(), 260.0, "torso")
    assert "face-on" in text and "trimmed 1s to end" in text
    assert "impact" in text and "Note: a note" in text
    assert "[FIX] Hands at impact: behind" in text
    assert "SUMMARY" in text and "- Hands at impact: behind" in text


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not on PATH")
def test_each_check_gets_its_own_key_frame(tmp_path):
    with VideoWriter(tmp_path / "normalized.mp4", 108, 192, 240.0) as w:
        for _ in range(100):
            w.write(np.zeros((192, 108, 3), np.uint8))
    a = Verdict(status="ok", label="a", summary="", phase="address", name="posture", title="Posture",
                overlays=[Overlay("point", [(30.0, 100.0)], (0, 0, 255))])
    b = Verdict(status="flag", label="b", summary="", phase="address", name="plane", title="Plane",
                overlays=[Overlay("point", [(80.0, 150.0)], (255, 0, 0))])
    ann = Annotator([a, b], PHASES, np.zeros((100, 2)), 240.0, 108, 192, CONFIG)
    written = write_outputs(tmp_path, ann, (5, 95), CONFIG, video=False)
    assert {"check_posture", "check_plane", "address"} <= set(written)  # two images on one frame
    import cv2

    posture = cv2.imread(str(written["check_posture"]))
    plane = cv2.imread(str(written["check_plane"]))
    assert posture[100, 30, 2] > 200 and plane[100, 30].max() < 50  # each shows only its own point
    assert plane[150, 80, 0] > 200 and posture[150, 80].max() < 50


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not on PATH")
def test_key_frame_on_a_marked_frame(tmp_path):
    # A check judged on a frame you marked (no detected phase) gets its key frame there.
    with VideoWriter(tmp_path / "normalized.mp4", 108, 192, 240.0) as w:
        for i in range(100):
            w.write(np.full((192, 108, 3), i * 2, np.uint8))
    v = Verdict(status="ok", label="a", summary="", phase=None, frame=77, name="halfway", title="Halfway")
    ann = Annotator([v], PHASES, np.zeros((100, 2)), 240.0, 108, 192, CONFIG)
    written = write_outputs(tmp_path, ann, (5, 50), CONFIG, video=False)
    import cv2

    img = cv2.imread(str(written["check_halfway"]))
    assert abs(int(img[96, 54].mean()) - 154) < 12  # frame 77's gray level, not another frame


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not on PATH")
def test_write_outputs_end_to_end(tmp_path):
    with VideoWriter(tmp_path / "normalized.mp4", 108, 192, 240.0) as w:
        for i in range(100):
            w.write(np.full((192, 108, 3), i * 2, np.uint8))
    pose = face_on_pose()
    hands = (pose.xy("left_wrist") + pose.xy("right_wrist")) / 2 / 10
    ann = Annotator([], PHASES, hands, 240.0, 108, 192, CONFIG)
    written = write_outputs(tmp_path, ann, (5, 95), CONFIG)
    assert set(written) == {"video", "address", "top", "impact", "summary"}
    for path in written.values():
        assert path.exists() and path.stat().st_size > 0


def test_video_header_names_only_checks_on_screen():
    early = Verdict(status="ok", label="a", summary="", name="early", title="Early",
                    overlays=[Overlay("point", [(10.0, 10.0)], frames=(0, 20))])
    late = Verdict(status="flag", label="b", summary="", name="late", title="Late",
                   overlays=[Overlay("point", [(10.0, 10.0)], frames=(50, 60))])
    broken = Verdict(status="error", label="no data", summary="", name="broken", title="Broken")
    ann = Annotator([early, late, broken], PHASES, np.zeros((100, 2)), 240.0, 100, 100, CONFIG)
    assert [v.name for v in ann._active(10)] == ["early"]
    assert [v.name for v in ann._active(55)] == ["late"]
    assert ann._active(35) == []
    assert [v.name for v in ann.only(late)._active(10)] == ["late"]  # a key frame always names its check


def test_whole_clip_overlays_dont_keep_a_check_in_the_header():
    plane = Verdict(status="ok", label="a", summary="", name="plane", title="Plane",
                    overlays=[Overlay("line", [(0.0, 0.0), (10.0, 10.0)], frames=(0, 99)),
                              Overlay("point", [(10.0, 10.0)], frames=(0, 10))])
    ann = Annotator([plane, plane], PHASES, np.zeros((100, 2)), 240.0, 100, 100, CONFIG)
    assert len(ann._active(5)) == 2      # its own lines are on screen
    assert ann._active(50) == []         # only the background line is


def test_marks_have_their_own_shapes():
    from swingcheck.analyzers import (PAST_COLOR, PLANE_COLOR, STATUS_COLORS, clubhead_mark, hands_mark,
                                      spot_mark)
    assert clubhead_mark((1, 2), STATUS_COLORS["ok"], None).kind == "circle"
    assert hands_mark((1, 2), STATUS_COLORS["ok"], None).kind == "square"
    assert spot_mark((1, 2), STATUS_COLORS["ok"], None).kind == "ring"
    # The plane and earlier-checkpoint colors stay clear of green / yellow / red.
    assert {PLANE_COLOR, PAST_COLOR}.isdisjoint(STATUS_COLORS.values())


def test_key_frames_are_saved_no_bigger_than_the_limit():
    from swingcheck.output.annotate import fit_within
    tall = np.zeros((3840, 2160, 3), np.uint8)
    assert fit_within(tall, 1920).shape == (1920, 1080, 3)
    assert fit_within(tall, 0) is tall  # 0 = full size
    small = np.zeros((1280, 720, 3), np.uint8)
    assert fit_within(small, 1920) is small  # never made bigger
