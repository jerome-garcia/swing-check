"""Camera check for a down-the-line clip, from the quick pose pass after upload.

Down-the-line means the camera straight behind the golfer's hands, looking at the
target, so the golfer is seen side-on: the shoulders and hips overlap left to right.
Seen from the front (or from well off to the side) they spread apart. Also checked:
how big they are in the frame, whether head or feet are cut off, and whether the body
is clear enough to track. Which way they face is measured separately (facing()) and
judged against the swing's handedness when it's shown (facing_finding()).

Each finding is {"level": "warn" | "flag", "title", "tip"} in plain words; no findings
means the camera looks right.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from swingcheck.models import LANDMARK_INDEX, PoseSeq

SAMPLES = 7  # detected frames nearest the address frame, medianed against jitter
# Body points for the clarity check. From behind, the far-side limb hides behind the near
# one, so each left/right pair counts its better-seen side.
TRACKED = ("shoulder", "hip", "knee", "ankle", "wrist")
BEHIND_TIP = "Put the camera straight behind your hands at about hip height, pointing at the target."


FRONT_TIP = "Put the camera straight in front of you at about hip height, lined up with the middle of your stance."
ANGLE_TITLES = ("This doesn't look like a down-the-line view", "The camera may be off to one side",
                "This doesn't look like a face-on view", "The camera may be at an angle")


def camera_check(pose: PoseSeq, address: int | None, config: dict[str, Any],
                 view: str | None = "dtl") -> list[dict[str, str]]:
    """Findings for the camera. `view` None leaves out the angle (angle_finding judges it
    later, from body_spread, for whichever view the swing ends up as)."""
    cfg = config["camera_check"]
    detected = np.where(pose.detected())[0]
    if not len(detected):
        return [finding("flag", "No golfer found",
                        "SwingCheck couldn't find a person in this clip. Check it's the right video, with your "
                        "whole body in view.")]
    near = detected[np.argsort(np.abs(detected - (address if address is not None else detected[0])))[:SAMPLES]]
    data = pose.data[near]

    def point(name: str) -> np.ndarray:
        return np.nanmedian(data[:, LANDMARK_INDEX[name], :2], axis=0)

    def visibility(part: str) -> float:
        """Tracker confidence for a body part: its better-seen side, for left/right pairs."""
        names = (f"left_{part}", f"right_{part}") if f"left_{part}" in LANDMARK_INDEX else (part,)
        return max(float(np.nanmedian(data[:, LANDMARK_INDEX[n], 3])) for n in names)

    findings = []
    shoulders = point("left_shoulder"), point("right_shoulder")
    hips = point("left_hip"), point("right_hip")
    shoulder_mid, hip_mid = (shoulders[0] + shoulders[1]) / 2, (hips[0] + hips[1]) / 2
    torso = float(np.linalg.norm(shoulder_mid - hip_mid))
    if not torso > 0:
        return [finding("flag", "Couldn't see your body clearly", BEHIND_TIP)]

    # Angle: side-to-side spread of shoulders and hips, as a share of torso length.
    spread = (abs(shoulders[0][0] - shoulders[1][0]) + abs(hips[0][0] - hips[1][0])) / 2 / torso
    if view is not None:
        findings += angle_finding(spread, view, config)

    # Framing: size, and head or feet cut off.
    top = min(point("nose")[1], point("left_ear")[1], point("right_ear")[1])
    bottom = max(point(n)[1] for n in ("left_ankle", "right_ankle", "left_heel", "right_heel"))
    margin = cfg["edge_margin"] * pose.height
    if top < margin:
        findings.append(finding("warn", "Your head is cut off",
                                "Keep your whole body in frame, with room above your head for the club at the top."))
    feet_seen = visibility("ankle") >= cfg["min_visibility"]
    if bottom > pose.height - margin or not feet_seen:
        findings.append(finding("warn", "Your feet are cut off or hidden",
                                "Keep your feet in frame: the checks measure your knees and hips from them."))
    elif (bottom - top) / pose.height < cfg["min_height"]:
        findings.append(finding("warn", "You're small in the frame",
                                "Move the camera closer, or zoom in, so you fill about half the frame's height. "
                                "Results are rougher when you're small."))

    # Clarity: how sure the tracker is about the main body points.
    if np.mean([visibility(part) for part in TRACKED]) < cfg["min_visibility"]:
        findings.append(finding("warn", "Your body is hard to see",
                                "Film in even light without strong light behind you, and wear clothes that stand "
                                "out from the background."))
    return findings


def body_spread(pose: PoseSeq, address: int | None) -> float | None:
    """Side-to-side spread of shoulders and hips near address, as a share of torso length:
    small from behind (down-the-line), large from the front (face-on)."""
    detected = np.where(pose.detected())[0]
    if not len(detected):
        return None
    near = detected[np.argsort(np.abs(detected - (address if address is not None else detected[0])))[:SAMPLES]]
    data = pose.data[near]

    def point(name: str) -> np.ndarray:
        return np.nanmedian(data[:, LANDMARK_INDEX[name], :2], axis=0)

    ls, rs, lh, rh = (point(n) for n in ("left_shoulder", "right_shoulder", "left_hip", "right_hip"))
    torso = float(np.linalg.norm((ls + rs) / 2 - (lh + rh) / 2))
    if not torso > 0:
        return None
    return round((abs(ls[0] - rs[0]) + abs(lh[0] - rh[0])) / 2 / torso, 3)


def angle_finding(spread: float, view: str, config: dict[str, Any]) -> list[dict[str, str]]:
    """Is the camera where this view needs it? Down-the-line wants a small spread, face-on a large one."""
    cfg = config["camera_check"]
    if view == "fo":
        if spread < cfg["face_on_flag"]:
            return [finding("flag", "This doesn't look like a face-on view",
                            "Face-on means the camera in front of you, facing your chest, so you're seen from the "
                            f"front. {FRONT_TIP}")]
        if spread < cfg["face_on_warn"]:
            return [finding("warn", "The camera may be at an angle",
                            f"Your shoulders and hips look narrower than they should from the front. {FRONT_TIP}")]
        return []
    if spread > cfg["side_on_flag"]:
        return [finding("flag", "This doesn't look like a down-the-line view",
                        "Down-the-line means the camera behind you, looking toward the target, so you're "
                        f"seen from the side. {BEHIND_TIP}")]
    if spread > cfg["side_on_warn"]:
        return [finding("warn", "The camera may be off to one side",
                        f"Your shoulders and hips look wider than they should from behind. {BEHIND_TIP}")]
    return []


MIN_RESPONSE = 0.1  # phase correlation's confidence below which an area's shift is ignored


def motion_from_frames(frames: Iterable[np.ndarray]) -> float:
    """How far the camera moved from the first frame (grayscale, float32) over the rest, as a
    share of the frame. Three areas that are mostly background (the top quarter, and the left
    and right sixths) are each lined up with the first frame (phase correlation); the median
    shift of the ones that line up with some confidence is the camera's, so the club or a
    passer-by crossing one area doesn't count (and a pan wider than an edge strip, which can't
    line up there, leaves the top quarter to say so). A shift only counts when it holds for two
    frames in a row."""
    it = iter(frames)
    ref = next(it, None)
    if ref is None:
        return 0.0
    h, w = ref.shape
    areas = [(slice(0, h // 4), slice(None)), (slice(None), slice(0, w // 6)), (slice(None), slice(5 * w // 6, None))]
    moved, last = 0.0, 0.0
    for frame in it:
        found = [cv2.phaseCorrelate(ref[r, c], frame[r, c]) for r, c in areas]
        shifts = [(np.hypot(dx / w, dy / h), response) for (dx, dy), response in found]
        # None lining up with confidence means the whole picture changed: use them all then.
        sure = [m for m, response in shifts if response >= MIN_RESPONSE] or [m for m, _ in shifts]
        now = float(np.median(sure))
        moved = max(moved, min(now, last))
        last = now
    return moved


def camera_motion(video: Path, start: int, fps: float, step_s: float) -> float:
    """motion_from_frames over the clip from the address frame, a frame every `step_s` seconds."""
    cap = cv2.VideoCapture(str(video))
    step = max(1, round(step_s * fps))

    def frames():
        i = 0
        while True:
            if not cap.grab():  # decode only the frames used
                return
            if i >= start and (i - start) % step == 0:
                ok, img = cap.retrieve()
                if ok:
                    yield cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
            i += 1

    try:
        return motion_from_frames(frames())
    finally:
        cap.release()


def motion_finding(moved: float, config: dict[str, Any]) -> list[dict[str, str]]:
    """The camera moving during the clip: every measurement compares positions in the picture,
    so a moving camera reads as the golfer moving."""
    cfg = config["camera_check"]
    tip = ("Put the phone on a tripod, or prop it against something solid, and don't zoom in or follow the swing: "
           "SwingCheck measures your body against the picture, so the camera has to stay still.")
    if moved >= cfg["moved_flag"]:
        return [finding("flag", "The camera moved during the clip", tip)]
    if moved >= cfg["moved_warn"]:
        return [finding("warn", "The camera may have moved during the clip", tip)]
    return []


def facing(pose: PoseSeq, address: int | None) -> int | None:
    """Which way the golfer faces at address: +1 right (nose ahead of the hips in x), -1 left.
    From behind the hands, a right-handed golfer faces right and a left-handed one left."""
    detected = np.where(pose.detected())[0]
    if not len(detected):
        return None
    near = detected[np.argsort(np.abs(detected - (address if address is not None else detected[0])))[:SAMPLES]]
    data = pose.data[near]
    nose = np.nanmedian(data[:, LANDMARK_INDEX["nose"], 0])
    hips = np.nanmedian(data[:, [LANDMARK_INDEX["left_hip"], LANDMARK_INDEX["right_hip"]], 0])
    side = np.sign(nose - hips)
    return int(side) if side else None


def facing_finding(side: int | None, handedness: str) -> dict[str, str] | None:
    """The "facing the wrong way" finding for a swing of this handedness, if it applies."""
    expected = 1 if handedness == "right" else -1
    if side is None or side == expected:
        return None
    other = "left" if handedness == "right" else "right"
    return finding("flag", f"You're facing {'left' if expected == 1 else 'right'}",
                   f"Filmed from behind your hands, a {handedness}-handed golfer faces "
                   f"{'right' if expected == 1 else 'left'} in the video. If you swing {other}-handed, switch "
                   f"this swing to {other}-handed. If not, the camera may be on the target side: move it behind "
                   "your hands.")


def finding(level: str, title: str, tip: str) -> dict[str, str]:
    return {"level": level, "title": title, "tip": tip}
