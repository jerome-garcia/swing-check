"""Pose extraction with MediaPipe PoseLandmarker, cached to runs/<clip>/pose.json.

The cache holds raw per-frame keypoints. Cleanup (filling short gaps,
smoothing) happens at load time in `clean_track`, so tuning those settings
never requires re-running the model.
"""

from __future__ import annotations

import contextlib
import json
import os
import sys
import tempfile
import urllib.request
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from swingcheck.config import PROJECT_ROOT
from swingcheck.ingest import VideoInfo
from swingcheck.models import LANDMARKS, SKELETON_EDGES, PoseSeq
from swingcheck.output.video import VideoWriter, iter_frames

MODELS_DIR = PROJECT_ROOT / "models"
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
    "pose_landmarker_{name}/float16/latest/pose_landmarker_{name}.task"
)
CACHE_VERSION = 1


def ensure_model(name: str) -> Path:
    """Path to the .task model file, downloading it once if missing."""
    if name not in ("lite", "full", "heavy"):
        raise ValueError(f"pose.model must be lite, full or heavy, not {name!r}")
    path = MODELS_DIR / f"pose_landmarker_{name}.task"
    if not path.exists():
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        url = MODEL_URL.format(name=name)
        print(f"Downloading pose model ({name}) from {url} ...")
        tmp = path.with_suffix(".part")
        urllib.request.urlretrieve(url, tmp)
        tmp.replace(path)
    return path


def _cache_params(info: VideoInfo, config: dict[str, Any]) -> dict[str, Any]:
    pose_cfg = config["pose"]
    return {
        "version": CACHE_VERSION,
        "video": {"width": info.width, "height": info.height, "fps": info.fps, "frame_count": info.frame_count,
                  "trim_start": info.trim_start, "trim_end": info.trim_end, "source_mtime": info.source_mtime},
        "model": pose_cfg["model"],
        "max_height": config["ingest"]["pose_max_height"],
        "min_detection_confidence": pose_cfg["min_detection_confidence"],
        "min_tracking_confidence": pose_cfg["min_tracking_confidence"],
        "trim": config["trim"],
    }


def save_pose(path: Path, pose: PoseSeq, params: dict[str, Any]) -> None:
    frames = []
    for frame in pose.data:
        if np.isnan(frame[0, 0]):
            frames.append(None)
        else:
            frames.append([[round(float(v), 2) if i < 2 else round(float(v), 4) for i, v in enumerate(lm)] for lm in frame])
    payload = {"params": params, "fps": pose.fps, "width": pose.width, "height": pose.height,
               "dense": list(pose.dense) if pose.dense else None,
               "landmarks": list(LANDMARKS), "frames": frames}
    path.write_text(json.dumps(payload, separators=(",", ":")))


def load_pose(path: Path) -> tuple[PoseSeq, dict[str, Any]]:
    payload = json.loads(path.read_text())
    n = len(payload["frames"])
    data = np.full((n, len(LANDMARKS), 4), np.nan)
    for i, frame in enumerate(payload["frames"]):
        if frame is not None:
            data[i] = frame
    dense = payload.get("dense")
    pose = PoseSeq(fps=payload["fps"], width=payload["width"], height=payload["height"], data=data,
                   dense=tuple(dense) if dense else None)
    return pose, payload["params"]


def extract_pose(
    video_path: Path,
    info: VideoInfo,
    config: dict[str, Any],
    select: Callable[[int], bool] | None = None,
    data: np.ndarray | None = None,
    label: str = "pose",
    progress: FrameProgress | None = None,
) -> np.ndarray:
    """Run PoseLandmarker on the frames `select` accepts (all by default), filling rows of `data`.

    Frames are downscaled for speed; coordinates come back in full-res pixels.
    Returns the (frames, 33, 4) array, NaN for frames not run or with no person.
    `progress(done, todo, label)` is called as frames complete (default: print).
    """
    with _native_stderr_captured():
        return _extract_pose(video_path, info, config, select, data, label, progress or _print_progress)


FrameProgress = Callable[[int, int, str], None]


def _print_progress(done: int, todo: int, label: str) -> None:
    print(f"\r  {label}: {done}/{todo} frames", end="\n" if done == todo else "", flush=True)


@contextlib.contextmanager
def _native_stderr_captured() -> Iterator[None]:
    """Hide MediaPipe's native log lines (written straight to fd 2); replay them if extraction fails."""
    sys.stderr.flush()
    saved = os.dup(2)
    with tempfile.TemporaryFile(mode="w+b") as tmp:
        os.dup2(tmp.fileno(), 2)
        try:
            yield
        except BaseException:
            os.dup2(saved, 2)
            tmp.seek(0)
            sys.stderr.write(tmp.read().decode(errors="replace"))
            raise
        finally:
            os.dup2(saved, 2)
            os.close(saved)


def _extract_pose(
    video_path: Path,
    info: VideoInfo,
    config: dict[str, Any],
    select: Callable[[int], bool] | None,
    data: np.ndarray | None,
    label: str,
    progress: FrameProgress,
) -> np.ndarray:
    # Imported here so the rest of the package (and tests) don't pay MediaPipe's import time.
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions, vision

    pose_cfg = config["pose"]
    options = vision.PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(ensure_model(pose_cfg["model"]))),
        running_mode=vision.RunningMode.VIDEO,
        num_poses=1,
        min_pose_detection_confidence=pose_cfg["min_detection_confidence"],
        min_pose_presence_confidence=pose_cfg["min_detection_confidence"],
        min_tracking_confidence=pose_cfg["min_tracking_confidence"],
    )
    max_h = config["ingest"]["pose_max_height"]
    scale = min(1.0, max_h / info.height) if max_h else 1.0
    size = (round(info.width * scale), round(info.height * scale))

    total_frames = info.frame_count or int(cv2.VideoCapture(str(video_path)).get(cv2.CAP_PROP_FRAME_COUNT))
    if data is None:
        data = np.full((total_frames, len(LANDMARKS), 4), np.nan)
    todo = sum(1 for i in range(total_frames) if select is None or select(i))
    done = 0
    progress(0, todo, label)
    with vision.PoseLandmarker.create_from_options(options) as landmarker:
        for i, frame in enumerate(iter_frames(video_path)):
            if i >= len(data):
                break
            if select is not None and not select(i):
                continue
            small = cv2.resize(frame, size, interpolation=cv2.INTER_AREA) if scale < 1.0 else frame
            rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
            image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            result = landmarker.detect_for_video(image, int(round(i * 1000 / info.fps)))
            data[i] = np.nan
            if result.pose_landmarks:
                for j, lm in enumerate(result.pose_landmarks[0]):
                    data[i, j] = (lm.x * info.width, lm.y * info.height, lm.z, lm.visibility)
            done += 1
            if done % 25 == 0 or done == todo:
                progress(done, todo, label)
    return data


SEGMENT_ALIGN = 16  # see segment_frame


def segment_frame(frame: np.ndarray, config: dict[str, Any]) -> np.ndarray:
    """Person silhouette for one BGR frame: (H, W) float mask, ~1 on the body, ~0 elsewhere."""
    with _native_stderr_captured():
        import mediapipe as mp
        from mediapipe.tasks.python import BaseOptions, vision

        pose_cfg = config["pose"]
        options = vision.PoseLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(ensure_model(pose_cfg["model"]))),
            running_mode=vision.RunningMode.IMAGE,
            num_poses=1,
            min_pose_detection_confidence=pose_cfg["min_detection_confidence"],
            output_segmentation_masks=True,
        )
        h, w = frame.shape[:2]
        max_h = config["ingest"]["pose_max_height"]
        scale = min(1.0, max_h / h) if max_h else 1.0
        small = cv2.resize(frame, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_AREA) if scale < 1 else frame
        # MediaPipe's segmentation hard-crashes the whole process (0xC0000409) on some
        # frame sizes, e.g. 640x1138. Padding to a multiple of 16 avoids it; the padding
        # is cropped off the mask again.
        sh, sw = small.shape[:2]
        padded = cv2.copyMakeBorder(small, 0, -sh % SEGMENT_ALIGN, 0, -sw % SEGMENT_ALIGN, cv2.BORDER_REPLICATE)
        with vision.PoseLandmarker.create_from_options(options) as landmarker:
            result = landmarker.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(padded, cv2.COLOR_BGR2RGB)))
    if not result.segmentation_masks:
        raise RuntimeError("no person found for segmentation")
    # Copy: numpy_view() points into MediaPipe's own buffer, which is freed with the
    # landmarker; reading a view of it later (when no resize below makes a copy, e.g.
    # a 576x1024 clip) crashes the whole process with an access violation.
    mask = np.array(result.segmentation_masks[0].numpy_view(), dtype=np.float32).squeeze()[:sh, :sw].copy()
    return cv2.resize(mask, (w, h), interpolation=cv2.INTER_LINEAR) if mask.shape != (h, w) else mask


def get_pose(
    run_dir: Path,
    info: VideoInfo,
    config: dict[str, Any],
    locate_swing: Callable[[PoseSeq], tuple[int, int] | None] | None = None,
    force: bool = False,
    progress: FrameProgress | None = None,
    extra_ranges: list[tuple[int, int]] | None = None,
) -> tuple[PoseSeq, bool]:
    """Cached pose if it matches the current video and pose settings, else extract and cache.

    With auto-trim on and a high frame rate clip, extraction runs in two passes:
    a quick pass at ~`trim.coarse_fps` over the whole clip, `locate_swing` finds
    the swing in it (returns a first/last frame range or None), then a full-rate
    pass fills in every frame of that range. Outside it, only the quick-pass
    frames have keypoints. `extra_ranges` (first, last) must be covered at full
    rate too, e.g. around the marked address frame; the full-rate pass is
    widened to include them rather than run separately, because every
    separate pass restarts the tracker and leaves a jump in the keypoints at
    its edges. Returns (pose, reused).
    """
    path = run_dir / "pose.json"
    extra = [(int(a), int(b)) for a, b in (extra_ranges or [])]
    params = {**_cache_params(info, config), "extra_ranges": [list(r) for r in extra]}
    if not force and path.exists():
        try:
            pose, cached_params = load_pose(path)
            if cached_params == params:
                return pose, True
        except (KeyError, ValueError, json.JSONDecodeError):
            pass

    video = run_dir / "normalized.mp4"
    trim_cfg = config["trim"]
    stride = max(1, round(info.fps / trim_cfg["coarse_fps"]))
    if trim_cfg["enabled"] and stride > 1 and locate_swing is not None:
        coarse = extract_pose(video, info, config, select=lambda i: i % stride == 0,
                              label="Quick pass to find the swing", progress=progress)
        found = locate_swing(PoseSeq(info.fps, info.width, info.height, coarse))
        if found is None:
            data = extract_pose(video, info, config, data=coarse,
                                label="Swing not located; processing every frame", progress=progress)
            dense = (0, len(data) - 1)
        else:
            pad_before = round(trim_cfg["pad_before_s"] * info.fps)
            pad_after = round(trim_cfg["pad_after_s"] * info.fps)
            first = min([found[0] - pad_before] + [a for a, _ in extra])
            last = max([found[1] + pad_after] + [b for _, b in extra])
            dense = (max(0, first), min(len(coarse) - 1, last))
            data = extract_pose(
                video, info, config, select=lambda i: dense[0] <= i <= dense[1], data=coarse,
                label="Tracking the swing", progress=progress,
            )
    else:
        data = extract_pose(video, info, config, label="Tracking the swing", progress=progress)
        dense = (0, len(data) - 1)

    pose = PoseSeq(fps=info.fps, width=info.width, height=info.height, data=data, dense=dense)
    save_pose(path, pose, params)
    return pose, False


def clean_track(xy: np.ndarray, fps: float, max_gap_ms: float, smoothing_ms: float) -> np.ndarray:
    """Fill NaN gaps up to `max_gap_ms` by linear interpolation, then centered moving-average smoothing.

    Longer gaps stay NaN. Smoothing averages only over valid samples, so it doesn't
    spread NaNs; a window of one frame or less leaves the track unchanged.
    """
    out = np.array(xy, dtype=float, copy=True)
    n = out.shape[0]
    max_gap = int(round(max_gap_ms * fps / 1000))
    for c in range(out.shape[1]):
        col = out[:, c]
        valid = ~np.isnan(col)
        if valid.sum() < 2:
            continue
        idx = np.arange(n)
        # Find runs of NaN strictly between valid samples.
        i = 0
        while i < n:
            if valid[i]:
                i += 1
                continue
            j = i
            while j < n and not valid[j]:
                j += 1
            if i > 0 and j < n and (j - i) <= max_gap:
                col[i:j] = np.interp(idx[i:j], [i - 1, j], [col[i - 1], col[j]])
            i = j

    half = int(round(smoothing_ms * fps / 1000 / 2))
    if half >= 1:
        kernel = np.ones(2 * half + 1)
        for c in range(out.shape[1]):
            col = out[:, c]
            valid = ~np.isnan(col)
            filled = np.where(valid, col, 0.0)
            sums = np.convolve(filled, kernel, mode="same")
            counts = np.convolve(valid.astype(float), kernel, mode="same")
            with np.errstate(invalid="ignore", divide="ignore"):
                smoothed = sums / counts
            out[:, c] = np.where(valid, smoothed, np.nan)
    return out


def write_debug_video(run_dir: Path, pose: PoseSeq, config: dict[str, Any]) -> Path:
    """Skeleton drawn over the normalized video, for checking tracking quality by eye."""
    out_path = run_dir / "pose_debug.mp4"
    min_vis = config["pose"]["min_visibility"]
    radius = max(2, round(pose.height / 300))
    with VideoWriter(out_path, pose.width, pose.height, pose.fps) as writer:
        for i, frame in enumerate(iter_frames(run_dir / "normalized.mp4")):
            if i < len(pose):
                _draw_skeleton(frame, pose.data[i], min_vis, radius)
            cv2.putText(frame, f"{i}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA)
            writer.write(frame)
    return out_path


def _draw_skeleton(frame: np.ndarray, landmarks: np.ndarray, min_vis: float, radius: int) -> None:
    if np.isnan(landmarks[0, 0]):
        cv2.putText(frame, "no pose", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2, cv2.LINE_AA)
        return
    index = {name: i for i, name in enumerate(LANDMARKS)}
    for a, b in SKELETON_EDGES:
        la, lb = landmarks[index[a]], landmarks[index[b]]
        if la[3] >= min_vis and lb[3] >= min_vis:
            cv2.line(frame, (int(la[0]), int(la[1])), (int(lb[0]), int(lb[1])), (0, 255, 0), 2, cv2.LINE_AA)
    for lm in landmarks:
        # Low-visibility points drawn red so tracking trouble is obvious.
        color = (0, 255, 255) if lm[3] >= min_vis else (0, 0, 255)
        cv2.circle(frame, (int(lm[0]), int(lm[1])), radius, color, -1, cv2.LINE_AA)
