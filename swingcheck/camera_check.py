"""Camera check for a down-the-line clip, from the quick pose pass after upload.

Down-the-line means the camera straight behind the golfer's hands, looking at the
target, so the golfer is seen side-on: the shoulders and hips overlap left to right.
Seen from the front (or from well off to the side) they spread apart. Also checked:
which way the golfer faces, how big they are in the frame, whether head or feet are
cut off, and whether the body is clear enough to track.

Each finding is {"level": "warn" | "flag", "title", "tip"} in plain words; no findings
means the camera looks right.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from swingcheck.models import LANDMARK_INDEX, PoseSeq

SAMPLES = 7  # detected frames nearest the address frame, medianed against jitter
# Body points for the clarity check. From behind, the far-side limb hides behind the near
# one, so each left/right pair counts its better-seen side.
TRACKED = ("shoulder", "hip", "knee", "ankle", "wrist")
BEHIND_TIP = "Put the camera straight behind your hands at about hip height, pointing at the target."


def camera_check(pose: PoseSeq, address: int | None, config: dict[str, Any]) -> list[dict[str, str]]:
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
    if spread > cfg["side_on_flag"]:
        findings.append(finding("flag", "This doesn't look like a down-the-line view",
                                "Down-the-line means the camera behind you, looking toward the target, so you're "
                                f"seen from the side. {BEHIND_TIP}"))
    elif spread > cfg["side_on_warn"]:
        findings.append(finding("warn", "The camera may be off to one side",
                                f"Your shoulders and hips look wider than they should from behind. {BEHIND_TIP}"))

    # Facing: from behind the hands, a right-handed golfer faces right in the video.
    expected = 1 if config["golfer"]["handedness"] == "right" else -1
    facing = np.sign(point("nose")[0] - hip_mid[0])
    if facing == -expected and spread <= cfg["side_on_flag"]:
        side = "right" if expected == 1 else "left"
        findings.append(finding("flag", f"You're facing {'left' if side == 'right' else 'right'}",
                                f"Filmed from behind your hands, a {config['golfer']['handedness']}-handed golfer faces "
                                f"{side} in the video. The camera may be on the target side: move it behind your hands."))

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


def finding(level: str, title: str, tip: str) -> dict[str, str]:
    return {"level": level, "title": title, "tip": tip}
