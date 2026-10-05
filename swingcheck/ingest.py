"""Normalize any ffmpeg-readable clip into a constant-frame-rate, upright H.264 MP4.

Metadata is optional: rotation is applied if the file has it, the frame rate is
taken from the stream (snapped to a standard rate when close), and anything
missing falls back to safe defaults with a warning rather than an error.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import asdict, dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

STANDARD_FPS = (24, 25, 30, 48, 50, 60, 100, 120, 240)
SNAP_TOLERANCE = 0.03  # snap to a standard rate within 3%
FALLBACK_FPS = 30.0
GAPPY_FRACTION = 0.9  # average below this share of a standard timeline rate = frames missing
HDR_TRANSFERS = {"arib-std-b67", "smpte2084"}  # HLG, PQ


class IngestError(RuntimeError):
    pass


@dataclass
class VideoInfo:
    source: str
    source_size: int
    source_mtime: float
    trim_start: float | None
    trim_end: float | None
    fps: float
    width: int
    height: int
    rotation: int
    frame_count: int
    duration: float
    source_codec: str
    hdr: bool
    warnings: list[str]

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(asdict(self), indent=2))

    @classmethod
    def load(cls, path: Path) -> "VideoInfo":
        return cls(**json.loads(path.read_text()))


def find_tool(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise IngestError(
            f"{name} not found on PATH. Install ffmpeg (e.g. `winget install Gyan.FFmpeg`) "
            "and open a new terminal."
        )
    return path


def parse_rate(text: str | None) -> float | None:
    """'30000/1001' -> 29.97; '0/0', '', None -> None."""
    if not text:
        return None
    try:
        value = float(Fraction(text))
    except (ValueError, ZeroDivisionError):
        return None
    return value if value > 0 else None


def snap_fps(fps: float) -> float:
    """Snap to a standard rate if within tolerance (e.g. 239.7 -> 240), else keep as-is."""
    for standard in STANDARD_FPS:
        if abs(fps - standard) / standard <= SNAP_TOLERANCE:
            return float(standard)
    return round(fps, 3)


def choose_fps(stream: dict[str, Any]) -> tuple[float, list[str]]:
    """Pick the constant output rate from what the stream reports.

    avg_frame_rate reflects the real capture rate for variable-rate phone video;
    r_frame_rate is the fallback (it can be a timebase-ish value like 90000 on VFR files).
    Exception: when r_frame_rate is a standard rate and the average is well below it,
    the file is on that timeline with frames missing (e.g. a shared iPhone slo-mo:
    60 fps with gaps averages 42). Converting at the average would throw away real
    frames, so the timeline rate is kept and the gaps repeat the previous frame.
    """
    warnings: list[str] = []
    avg = parse_rate(stream.get("avg_frame_rate"))
    real = parse_rate(stream.get("r_frame_rate"))
    candidates = [r for r in (avg, real) if r is not None and 1 <= r <= 1000]
    if not candidates:
        warnings.append(f"No usable frame rate in file; assuming {FALLBACK_FPS:g} fps.")
        return FALLBACK_FPS, warnings
    if avg is not None and real is not None and snap_fps(real) in STANDARD_FPS and avg < GAPPY_FRACTION * real:
        warnings.append(
            f"Frames are missing in this file (it averages {avg:.0f} fps on a {snap_fps(real):g} fps "
            "timeline); the gaps repeat the previous frame."
        )
        return snap_fps(real), warnings
    return snap_fps(candidates[0]), warnings


def parse_rotation(stream: dict[str, Any]) -> int:
    """Rotation in degrees (0/90/180/270) from display-matrix side data or legacy tag; 0 if absent."""
    raw: Any = None
    for side in stream.get("side_data_list", []) or []:
        if "rotation" in side:
            raw = side["rotation"]
            break
    if raw is None:
        raw = (stream.get("tags") or {}).get("rotate")
    try:
        return int(round(float(raw))) % 360 if raw is not None else 0
    except (TypeError, ValueError):
        return 0


def probe(path: Path) -> dict[str, Any]:
    cmd = [
        find_tool("ffprobe"), "-v", "error", "-print_format", "json",
        "-show_streams", "-show_format", str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise IngestError(f"ffprobe could not read {path}: {result.stderr.strip()}")
    return json.loads(result.stdout)


def video_stream(probe_data: dict[str, Any]) -> dict[str, Any]:
    for stream in probe_data.get("streams", []):
        if stream.get("codec_type") == "video" and not (stream.get("disposition") or {}).get("attached_pic"):
            return stream
    raise IngestError("No video stream found.")


def _is_cached(info_path: Path, out_path: Path, source: Path, start: float | None, end: float | None) -> bool:
    if not (info_path.exists() and out_path.exists()):
        return False
    try:
        info = VideoInfo.load(info_path)
    except (TypeError, ValueError, json.JSONDecodeError):
        return False
    stat = source.stat()
    return (
        info.source_size == stat.st_size
        and abs(info.source_mtime - stat.st_mtime) < 1e-3
        and info.trim_start == start
        and info.trim_end == end
    )


def normalize(
    source: Path,
    run_dir: Path,
    config: dict[str, Any],
    start: float | None = None,
    end: float | None = None,
    force: bool = False,
    progress: Callable[[float], None] | None = None,
) -> VideoInfo:
    """Write run_dir/normalized.mp4 and run_dir/video.json; reuse them if the input is unchanged.

    `progress(fraction)` is called as ffmpeg works through the clip.
    """
    run_dir.mkdir(parents=True, exist_ok=True)
    out_path = run_dir / "normalized.mp4"
    info_path = run_dir / "video.json"
    if not force and _is_cached(info_path, out_path, source, start, end):
        return VideoInfo.load(info_path)

    data = probe(source)
    stream = video_stream(data)
    fps, warnings = choose_fps(stream)
    rotation = parse_rotation(stream)
    hdr = stream.get("color_transfer") in HDR_TRANSFERS

    ingest_cfg = config["ingest"]
    if fps <= ingest_cfg["low_fps_warning"]:
        warnings.append(
            f"Filmed at {fps:g} fps. That works, but slo-mo (120-240 fps) pins down impact more "
            "precisely. If you did film slo-mo, upload the original file rather than a shared copy "
            "(see Filming in the README)."
        )
    if hdr:
        warnings.append("HDR clip: converted to SDR without tone mapping, colors may look flat (pose is unaffected).")

    # ffmpeg auto-rotates on decode and drops the rotation tag on output, so the
    # result is upright pixels with no display matrix.
    cmd = [find_tool("ffmpeg"), "-v", "error", "-y"]
    if start is not None:
        cmd += ["-ss", f"{start:.3f}"]
    if end is not None:
        cmd += ["-to", f"{end:.3f}"]
    cmd += [
        "-i", str(source),
        "-map", "0:v:0", "-an",
        "-vf", f"fps={fps:g}",
        "-fps_mode", "cfr",
        "-c:v", "libx264", "-preset", "fast", "-crf", str(ingest_cfg["crf"]),
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-progress", "pipe:1", "-nostats",
        str(out_path),
    ]
    # Expected output length, for progress: the trimmed span of the source.
    src_duration = float((data.get("format") or {}).get("duration") or 0.0)
    span = (end if end is not None else src_duration) - (start or 0.0)
    _run_with_progress(cmd, span, progress)

    out_stream = video_stream(probe_output(out_path))
    stat = source.stat()
    info = VideoInfo(
        source=str(source.resolve()),
        source_size=stat.st_size,
        source_mtime=stat.st_mtime,
        trim_start=start,
        trim_end=end,
        fps=fps,
        width=int(out_stream["width"]),
        height=int(out_stream["height"]),
        rotation=rotation,
        frame_count=int(out_stream.get("nb_frames") or 0),
        duration=float(out_stream.get("duration") or 0.0),
        source_codec=str(stream.get("codec_name", "unknown")),
        hdr=hdr,
        warnings=warnings,
    )
    info.save(info_path)
    return info


def _run_with_progress(cmd: list[str], duration_s: float, progress: Callable[[float], None] | None) -> None:
    """Run ffmpeg with `-progress pipe:1`, reporting the fraction of `duration_s` done."""
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert proc.stdout is not None
    for line in proc.stdout:
        key, _, value = line.strip().partition("=")
        if progress is not None and key == "out_time_us" and duration_s > 0:
            try:
                progress(min(1.0, max(0.0, int(value) / 1e6 / duration_s)))
            except ValueError:
                pass
    stderr = proc.stderr.read() if proc.stderr else ""
    if proc.wait() != 0:
        raise IngestError(f"ffmpeg failed: {stderr.strip()}")


def probe_output(path: Path) -> dict[str, Any]:
    cmd = [
        find_tool("ffprobe"), "-v", "error", "-count_packets", "-print_format", "json",
        "-show_streams", str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise IngestError(f"ffprobe could not read {path}: {result.stderr.strip()}")
    data = json.loads(result.stdout)
    for stream in data.get("streams", []):
        if "nb_read_packets" in stream and not stream.get("nb_frames"):
            stream["nb_frames"] = stream["nb_read_packets"]
    return data
