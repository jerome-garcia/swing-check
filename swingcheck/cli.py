"""Command-line entry point: a thin wrapper over swingcheck.pipeline.

(Being replaced by the web app.)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from swingcheck.config import PROJECT_ROOT, load_config
from swingcheck.ingest import IngestError
from swingcheck.marking import MarkingCancelled, get_marks
from swingcheck.output.report import STATUS_TAGS
from swingcheck.pipeline import PipelineError, analyze, ingest


def _print_progress(stage: str, fraction: float | None, message: str) -> None:
    if stage == "pose":
        print(f"\r  {message}", end="\n" if fraction == 1.0 else "", flush=True)
    elif stage != "done":
        print(f"{message}...")


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
    parser.add_argument("--no-video", action="store_true", help="skip the annotated video (images and report only)")
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
        info = ingest(args.video, run_dir, config, start=args.start, end=args.end, force=args.force)
        for warning in info.warnings:
            print(f"warning: {warning}")
        get_marks(run_dir / "normalized.mp4", run_dir, args.view, info, config, remark=args.remark)
        overrides = {k: v for k, v in (("address", args.address), ("top", args.top), ("impact", args.impact))
                     if v is not None}
        result = analyze(run_dir, args.view, config, overrides=overrides, clear_overrides=args.auto_phases,
                         force=args.force, video=not args.no_video, pose_debug=args.pose_debug,
                         progress=_print_progress)
    except MarkingCancelled:
        print("Marking cancelled; nothing saved.", file=sys.stderr)
        return 1
    except (IngestError, PipelineError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    for warning in result.warnings:
        if warning not in info.warnings:
            print(f"warning: {warning}")
    print("Phases:")
    for name, frame in result.phases.as_dict().items():
        tag = "  (manual)" if name in result.phases.manual else ""
        print(f"  {name:<16} frame {frame:>5}  {frame / result.pose.fps:6.2f}s{tag}")
    print("Results:")
    for v in result.verdicts:
        print(f"  [{STATUS_TAGS[v.status]:<5}] {v.title}: {v.label}")
        print(f"          {v.summary}")
    for name, path in result.written.items():
        print(f"  {name:<8} {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
