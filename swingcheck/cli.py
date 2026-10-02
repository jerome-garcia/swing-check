"""Command-line entry point. Pipeline stages are wired in as they're built."""

from __future__ import annotations

import argparse
from pathlib import Path

from swingcheck.config import load_config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="swingcheck", description="Analyze one golf swing video.")
    parser.add_argument("video", type=Path, help="input video (.mov/.mp4)")
    parser.add_argument("--view", required=True, choices=["dtl", "fo"], help="camera view")
    parser.add_argument("--config", type=Path, help="extra TOML file overriding config values")
    args = parser.parse_args(argv)

    if not args.video.exists():
        parser.error(f"video not found: {args.video}")
    load_config(args.config)
    print(f"Loaded config; analysis stages not implemented yet ({args.view}: {args.video}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
