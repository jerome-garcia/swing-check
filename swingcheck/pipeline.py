"""The analysis pipeline as reusable stages, independent of the UI.

    info = ingest(video, run_dir, config, start, end)        # normalize + trim
    save_marks(run_dir, view, address_frame, points, info)    # from the marking screen
    result = analyze(run_dir, view, config)                   # pose -> phases -> checks -> outputs

Each stage reports progress through an optional callback
`progress(stage, fraction, message)`, where fraction is 0-1 or None when unknown.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from swingcheck.analyzers import SwingContext, Verdict, run_analyzers
from swingcheck.body import body_scale, hands
from swingcheck.ingest import VideoInfo, normalize
from swingcheck.models import CHECKPOINT_MARKS, REQUIRED_MARKS, CheckpointMark, Marks, Point, PoseSeq
from swingcheck.output.annotate import Annotator, write_outputs
from swingcheck.output.report import build_report
from swingcheck.phases import PhaseError, Phases, detect_phases, get_phases
from swingcheck.pose import get_pose, write_debug_video

ProgressFn = Callable[[str, float | None, str], None]


class PipelineError(RuntimeError):
    """A stage can't run; the message says what the user needs to do."""


def _noop(stage: str, fraction: float | None, message: str) -> None:
    pass


def video_signature(info: VideoInfo) -> dict[str, float | int | None]:
    """Identifies a normalized video, so marks/overrides made on a different trim are not reused."""
    return {
        "width": info.width,
        "height": info.height,
        "fps": info.fps,
        "frame_count": info.frame_count,
        "trim_start": info.trim_start,
        "trim_end": info.trim_end,
    }


def load_marks(path: Path, view: str, info: VideoInfo) -> Marks | None:
    """Saved marks if they exist and still match this view and normalized video, else None."""
    if not path.exists():
        return None
    try:
        marks = Marks.load(path)
    except (KeyError, TypeError, ValueError):
        return None
    if marks.view != view or marks.video_signature != video_signature(info) or not marks.is_complete():
        return None
    return marks


def ingest(source: Path, run_dir: Path, config: dict[str, Any], start: float | None = None,
           end: float | None = None, force: bool = False, progress: ProgressFn | None = None) -> VideoInfo:
    progress = progress or _noop
    progress("normalize", 0.0, "Converting video")
    info = normalize(source, run_dir, config, start=start, end=end, force=force,
                     progress=lambda f: progress("normalize", f, "Converting video"))
    progress("normalize", 1.0, f"{info.width}x{info.height} @ {info.fps:g} fps, {info.frame_count} frames")
    return info


def save_marks(run_dir: Path, view: str, address_frame: int, points: dict[str, Point], info: VideoInfo,
               checkpoints: dict[str, dict[str, Any]] | None = None) -> Marks:
    """Save the address marks, plus optional checkpoint marks such as
    {"takeaway": {"frame": 195, "points": {"clubhead": (x, y), "grip": (x, y)}}}."""
    missing = [name for name in REQUIRED_MARKS[view] if name not in points]
    if missing:
        raise PipelineError(f"Missing marks: {', '.join(missing)}")
    frame_count = max(1, info.frame_count)
    if not 0 <= address_frame < frame_count:
        raise PipelineError(f"Address frame {address_frame} is outside the clip")
    kept: dict[str, CheckpointMark] = {}
    for name, cp in (checkpoints or {}).items():
        allowed = CHECKPOINT_MARKS[view].get(name)
        if allowed is None:
            raise PipelineError(f"Unknown checkpoint marks: {name}")
        cp_points = {k: (float(x), float(y)) for k, (x, y) in (cp.get("points") or {}).items() if k in allowed}
        if not cp_points:
            continue  # nothing clicked for this checkpoint yet
        frame = int(cp["frame"])
        if not 0 <= frame < frame_count:
            raise PipelineError(f"{name.capitalize()} frame {frame} is outside the clip")
        if frame <= address_frame:
            raise PipelineError(f"The {name} frame must come after the address frame")
        kept[name] = CheckpointMark(frame=frame, points=cp_points)
    marks = Marks(view=view, address_frame=int(address_frame),
                  points={k: (float(x), float(y)) for k, (x, y) in points.items() if k in REQUIRED_MARKS[view]},
                  video_signature=video_signature(info), checkpoints=kept)
    marks.save(run_dir / "marks.json")
    return marks


def _downswing_search(pose: PoseSeq) -> tuple[int, int] | None:
    """Where to look for the downswing: the full-rate stretch, a few frames in from its
    edges, where it meets the quick-pass frames (the tracker restart leaves a jump there)."""
    if not pose.dense or pose.dense == (0, len(pose) - 1):
        return None
    margin = max(3, round(0.03 * pose.fps))
    lo, hi = pose.dense[0] + margin, pose.dense[1] - margin
    return (lo, hi) if hi > lo else None


@dataclass
class AnalysisResult:
    info: VideoInfo
    marks: Marks
    pose: PoseSeq
    phases: Phases
    verdicts: list[Verdict]
    scale: float
    warnings: list[str] = field(default_factory=list)
    written: dict[str, Path] = field(default_factory=dict)


def analyze(
    run_dir: Path,
    view: str,
    config: dict[str, Any],
    overrides: dict[str, int] | None = None,
    clear_overrides: bool = False,
    force: bool = False,
    video: bool = True,
    pose_debug: bool = False,
    progress: ProgressFn | None = None,
) -> AnalysisResult:
    """Pose -> phases -> checks -> outputs for a run that has been ingested and marked."""
    progress = progress or _noop
    info_path = run_dir / "video.json"
    if not info_path.exists():
        raise PipelineError("This swing hasn't been converted yet.")
    info = VideoInfo.load(info_path)
    marks = load_marks(run_dir / "marks.json", view, info)
    if marks is None:
        raise PipelineError("Mark the ball (and club, for DTL) before analyzing.")

    def locate_swing(coarse: PoseSeq) -> tuple[int, int] | None:
        try:
            scale = body_scale(coarse, marks.address_frame, config)
            found = detect_phases(hands(coarse, config), coarse.fps, scale, config["phases"])
        except (PhaseError, ValueError):
            return None
        return found.address, found.impact

    def pose_progress(done: int, todo: int, label: str) -> None:
        progress("pose", done / todo if todo else None, f"{label}: {done}/{todo} frames")

    progress("pose", 0.0, "Finding your body in each frame")
    # The marked address frame can sit well before the swing; always track around it.
    around = round(0.25 * info.fps)
    address_range = (max(0, marks.address_frame - around), marks.address_frame + around)
    pose, _ = get_pose(run_dir, info, config, locate_swing=locate_swing, force=force, progress=pose_progress,
                       extra_ranges=[address_range])

    progress("phases", None, "Finding address, top and impact")
    warnings: list[str] = list(info.warnings)
    hand_track = hands(pose, config)
    try:
        scale = body_scale(pose, marks.address_frame, config)
        # DTL posture checks are judged on the frame the user marked, so it is the address.
        phases, detect_error = get_phases(
            run_dir, hand_track, pose.fps, scale, config, video_signature(info), overrides or {}, clear_overrides,
            marked_address=marks.address_frame if view == "dtl" else None,
            search=_downswing_search(pose),
            marked_takeaway=marks.checkpoint("takeaway").frame if marks.checkpoint("takeaway") else None,
        )
    except (PhaseError, ValueError) as e:
        raise PipelineError(f"{e} Set the phase frames manually.") from e
    takeaway_mark = marks.checkpoint("takeaway")
    if takeaway_mark and phases.takeaway != takeaway_mark.frame:
        warnings.append("The takeaway frame you marked isn't between address and the top, so it was ignored.")
    if detect_error:
        warnings.append(f"Automatic phase detection failed ({detect_error}); using the frames you set.")
    detected = pose.detected()
    untracked = [name for name, f in phases.as_dict().items() if not detected[f]]
    if untracked:
        warnings.append(f"No body tracked at {', '.join(untracked)}; checks there may be missing or rough.")

    progress("checks", None, "Running checks")
    ctx = SwingContext(
        view=view, pose=pose, marks=marks, phases=phases,
        scale=body_scale(pose, phases.address, config), config=config,
        video_path=run_dir / "normalized.mp4",
    )
    verdicts = run_analyzers(ctx)
    (run_dir / "analysis.json").write_text(json.dumps(
        {"view": view, "phases": phases.as_dict(), "manual_phases": phases.manual, "fps": pose.fps,
         "body_scale_px": round(ctx.scale, 2), "warnings": warnings,
         "verdicts": [v.to_json() for v in verdicts]},
        indent=2, default=float,
    ))
    report = build_report(Path(info.source), view, info, phases, verdicts, ctx.scale, config["scale"]["method"])
    (run_dir / "report.txt").write_text(report, encoding="utf-8")

    progress("outputs", None, "Drawing the annotated video")
    annotator = Annotator(verdicts, phases, hand_track, pose.fps, info.width, info.height, config)
    frame_range = pose.dense if pose.dense else (0, len(pose) - 1)
    written = write_outputs(run_dir, annotator, frame_range, config, video=video)
    written["report"] = run_dir / "report.txt"
    if pose_debug:
        written["debug"] = write_debug_video(run_dir, pose, config)
    progress("done", 1.0, "Done")
    return AnalysisResult(info=info, marks=marks, pose=pose, phases=phases, verdicts=verdicts,
                          scale=ctx.scale, warnings=warnings, written=written)
