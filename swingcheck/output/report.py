"""Plain-text report: clip info, phases, and each analyzer's verdict with its numbers."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from swingcheck.analyzers import Verdict
from swingcheck.ingest import VideoInfo
from swingcheck.phases import Phases

STATUS_TAGS = {"ok": "OK", "warn": "WATCH", "flag": "FLAG", "error": "ERROR"}


def build_report(video: Path, view: str, info: VideoInfo, phases: Phases, verdicts: list[Verdict],
                 scale_px: float, scale_method: str) -> str:
    view_name = {"dtl": "down-the-line", "fo": "face-on"}[view]
    trim = ""
    if info.trim_start is not None or info.trim_end is not None:
        end = f"{info.trim_end:g}s" if info.trim_end is not None else "end"
        trim = f" (trimmed {info.trim_start or 0:g}s to {end})"
    out = [
        f"swingcheck report: {video.name}",
        f"{datetime.now():%Y-%m-%d %H:%M}   view: {view_name}",
        f"{info.width}x{info.height} @ {info.fps:g} fps, {info.frame_count} frames{trim}",
        f"Body scale: {scale_method.replace('_', ' ')} = {scale_px:.0f} px at address "
        "(distances below are in multiples of this)",
    ]
    for w in info.warnings:
        out.append(f"Note: {w}")

    out += ["", "PHASES"]
    for name, frame in phases.as_dict().items():
        tag = "  (set manually)" if name in phases.manual else ""
        out.append(f"  {name.replace('_', ' '):<16} frame {frame:>5}   {frame / info.fps:7.3f}s{tag}")

    out += ["", "RESULTS"]
    if not verdicts:
        out.append("  (no analyzers for this view)")
    flagged = [v for v in verdicts if v.status in ("flag", "warn")]
    for v in verdicts:
        out.append(f"  [{STATUS_TAGS[v.status]}] {v.title}: {v.label}")
        out.append(f"      {v.summary}")
        for key, value in v.measurements.items():
            if key in ("units", "traceback"):
                continue
            out.append(f"      {key.replace('_', ' ')}: {value}")
        if "units" in v.measurements:
            out.append(f"      ({v.measurements['units']})")
        out.append("")

    out.append("SUMMARY")
    if flagged:
        for v in flagged:
            out.append(f"  - {v.title}: {v.label}")
    elif verdicts:
        out.append("  Nothing flagged.")
    out += ["", "Thresholds live in config/default.toml; override them in config/local.toml."]
    return "\n".join(out) + "\n"
