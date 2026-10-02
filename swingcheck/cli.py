"""Command-line entry point. Pipeline stages are wired in as they're built."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from swingcheck.config import PROJECT_ROOT, load_config
from swingcheck.ingest import IngestError, normalize
from swingcheck.marking import MarkingCancelled, get_marks


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
    print(f"Output: {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
