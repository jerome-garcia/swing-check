"""Command-line entry point. Pipeline stages are wired in as they're built."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from swingcheck.config import PROJECT_ROOT, load_config
from swingcheck.ingest import IngestError, normalize
from swingcheck.body import body_scale, hands
from swingcheck.marking import MarkingCancelled, get_marks, video_signature
from swingcheck.models import PoseSeq
from swingcheck.phases import PhaseError, detect_phases, get_phases
from swingcheck.pose import get_pose, write_debug_video


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="swingcheck", description="Analyze one golf swing video.")
    parser.add_argument("video", type=Path, help="input video (any format ffmpeg reads, e.g. .mov/.mp4)")
    parser.add_argument("--view", required=True, choices=["dtl", "fo"], help="camera view")
    parser.add_argument("--start", type=float, help="trim: start time in seconds")
    parser.add_argument("--end", type=float, help="trim: end time in seconds")
    parser.add_argument("--config", type=Path, help="extra TOML file overriding config values")
    parser.add_argument("--runs-dir", type=Path, default=PROJECT_ROOT / "runs", help="where outputs go")
    parser.add_argument("--force", action="store_true", help="ignore cached results and redo every stage")
    parser.add_argument("--remark", action="store_true", help="re-open the marking window even if marks are saved")
    parser.add_argument("--pose-debug", action="store_true", help="also write pose_debug.mp4 with the skeleton drawn")
    phase_args = parser.add_argument_group("phase overrides (frame numbers; saved for later runs)")
    phase_args.add_argument("--address", type=int, help="address frame")
    phase_args.add_argument("--top", type=int, help="top-of-backswing frame")
    phase_args.add_argument("--impact", type=int, help="impact frame")
    phase_args.add_argument("--auto-phases", action="store_true", help="discard saved overrides, use detection only")
    args = parser.parse_args(argv)

    if not args.video.exists():
        parser.error(f"video not found: {args.video}")
    if args.start is not None and args.end is not None and args.end <= args.start:
        parser.error("--end must be after --start")
    config = load_config(args.config)
    run_dir = args.runs_dir / args.video.stem

    try:
        info = normalize(args.video, run_dir, config, start=args.start, end=args.end, force=args.force)
    except IngestError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    print(
        f"Normalized: {info.width}x{info.height} @ {info.fps:g} fps, "
        f"{info.frame_count} frames ({info.duration:.2f}s), rotation applied: {info.rotation} deg"
    )
    for warning in info.warnings:
        print(f"warning: {warning}")

    try:
        marks, reused = get_marks(run_dir / "normalized.mp4", run_dir, args.view, info, config, remark=args.remark)
    except MarkingCancelled:
        print("Marking cancelled; nothing saved.", file=sys.stderr)
        return 1
    source = "reused saved marks" if reused else "saved marks"
    points = ", ".join(f"{name}=({x:.0f},{y:.0f})" for name, (x, y) in marks.points.items())
    print(f"Marks ({source}): address frame {marks.address_frame}, {points}")

    def locate_swing(coarse: PoseSeq) -> tuple[int, int] | None:
        try:
            scale = body_scale(coarse, marks.address_frame, config)
            found = detect_phases(hands(coarse, config), coarse.fps, scale, config["phases"])
        except (PhaseError, ValueError):
            return None
        return found.address, found.impact

    pose, reused = get_pose(run_dir, info, config, locate_swing=locate_swing, force=args.force)
    if pose.dense and pose.dense != (0, len(pose) - 1):
        span = f", full-rate frames {pose.dense[0]}-{pose.dense[1]}"
    else:
        span = ""
    print(f"Pose ({'reused cache' if reused else 'extracted'}){span}")

    overrides = {k: v for k, v in (("address", args.address), ("top", args.top), ("impact", args.impact)) if v is not None}
    hand_track = hands(pose, config)
    try:
        scale = body_scale(pose, marks.address_frame, config)
        phases, detect_error = get_phases(
            run_dir, hand_track, pose.fps, scale, config, video_signature(info), overrides, args.auto_phases
        )
    except (PhaseError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        print("Set phase frames manually with --address N --top N --impact N (frame numbers).", file=sys.stderr)
        return 1
    if detect_error:
        print(f"warning: automatic phase detection failed ({detect_error}); using manual frames")
    print("Phases:")
    for name, frame in phases.as_dict().items():
        tag = "  (manual)" if name in phases.manual else ""
        print(f"  {name:<16} frame {frame:>5}  {frame / pose.fps:6.2f}s{tag}")
    if pose.dense and not all(pose.dense[0] <= f <= pose.dense[1] for f in phases.as_dict().values()):
        print("warning: a phase lies outside the full-rate pose range; rerun with --force to re-extract around it")

    if args.pose_debug:
        print(f"Debug video: {write_debug_video(run_dir, pose, config)}")
    print(f"Output: {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
