"""Down-the-line checkpoint 5: top of the backswing.

On the top frame you mark, using the hands you click there:

  lead arm   the lead arm (lead shoulder -> hands) should match the shoulders:
             about 90° to the spine. The spine is drawn from the hip center
             through the head (between the ears), the way golf instruction
             draws the spine angle; a line to the middle of the shoulders
             comes out too upright at the top, because the turned shoulders'
             midpoint slides across the upper back. Under 90° = arm above the
             shoulder plane (lifted, upright); over 90° = below it (flat,
             around the body).

Body points come from tracking. Bands are in [analyzers.top]. (A "hands in the
plane zone" check was tried here and dropped at the user's request.)
"""

from __future__ import annotations

import numpy as np

from swingcheck.analyzers import (REFERENCE_COLOR, STATUS_COLORS, MissingData, Overlay, Row, SwingContext, Verdict, grade,
                                  register)
from swingcheck.analyzers.dtl_swing_plane import swing_plane_line
from swingcheck.geometry import angle_between_deg

HOLD_MS = 400


@register("top", view="dtl", title="Top", phase="top")
def top(ctx: SwingContext) -> Verdict:
    mark = ctx.marks.checkpoint("top")
    if mark is None:
        raise MissingData("the top isn't marked yet: Edit marks → Top, then click the clubhead and hands")
    cfg = ctx.cfg
    f = mark.frame
    clubhead = np.asarray(mark.points["clubhead"], float)
    hands = np.asarray(mark.points["grip"], float)
    ball = np.asarray(ctx.marks.points["ball"], float)

    hip0 = ctx.midpoint("left_hip", "right_hip")[ctx.marks.address_frame]
    if not np.all(np.isfinite(hip0)):
        hip0 = ctx.value(ctx.track(ctx.side("hip", "trail")), ctx.marks.address_frame, "trail hip")
    toward_golfer = -1.0 if hip0[0] < ball[0] else 1.0

    # Lead arm vs spine on the top frame.
    lead_shoulder = ctx.value(ctx.track(ctx.side("shoulder", "lead")), f, "lead shoulder")
    hip_mid = ctx.midpoint("left_hip", "right_hip")[f]
    # Spine: hip center through the head (between the ears; the nose if the ears are lost).
    head = ctx.midpoint("left_ear", "right_ear")[f]
    if not np.all(np.isfinite(head)):
        head = ctx.track("nose")[f]
    if not (np.all(np.isfinite(head)) and np.all(np.isfinite(hip_mid))):
        raise MissingData(f"head or hips not tracked on the top frame ({f})")
    arm_angle = angle_between_deg(hands - lead_shoulder, head - hip_mid)
    status = grade(arm_angle, cfg["arm_spine_min"], cfg["arm_spine_max"],
                   cfg["arm_spine_watch_min"], cfg["arm_spine_watch_max"])
    soft = status == "warn"
    if status == "ok":
        label, meaning = "Lead arm matches the shoulders", "your lead arm is square to your spine, on the shoulder plane"
        tip = ""
    elif arm_angle < cfg["arm_spine_min"]:
        label = "Lead arm slightly above the shoulders" if soft else "Lead arm above the shoulders"
        meaning = "your lead arm is lifted above the shoulder plane (upright)"
        tip = "Turn your shoulders more and keep the lead arm across your chest instead of lifting it."
    else:
        label = "Lead arm slightly below the shoulders" if soft else "Lead arm below the shoulders"
        meaning = "your lead arm is below the shoulder plane (flat, around your body)"
        tip = "Swing the lead arm a little higher so it matches your shoulder turn."

    # Drawing: the spine, the lead arm, and a dashed target arm square to the spine.
    s = ctx.scale
    show = (f, min(len(ctx.pose) - 1, f + int(round(HOLD_MS * ctx.fps / 1000))))
    col = STATUS_COLORS[status]
    spine = head - hip_mid
    square = np.array([-spine[1], spine[0]]) / np.linalg.norm(spine)
    if np.dot(square, hands - lead_shoulder) < 0:
        square = -square
    target = lead_shoulder + square * np.linalg.norm(hands - lead_shoulder)
    overlays = [
        Overlay("segment", [tuple(hip_mid), tuple(head)], REFERENCE_COLOR, "", show, 2),
        Overlay("segment", [tuple(lead_shoulder), tuple(hands)], col, "", show, 3),
        Overlay("dashed", [tuple(lead_shoulder), tuple(target)], STATUS_COLORS["ok"], "90 deg" if status != "ok" else "",
                show, 2),
        Overlay("point", [tuple(hands)], col, "", show, 2),
        Overlay("point", [tuple(clubhead)], REFERENCE_COLOR, "", show, 1),
        Overlay("text", [(float(lead_shoulder[0]) - toward_golfer * 0.1 * s, float(lead_shoulder[1]) + 0.2 * s)], col,
                f"arm {arm_angle:.0f} deg", show),
    ]

    return Verdict(
        status=status,
        label=label,
        summary=f"At the top, {meaning}.",
        tip=tip,
        frame=f,
        measurements={
            "arm_to_spine_deg": round(arm_angle, 1),
            "top_frame": f,
            "units": "degrees between the lead arm and the spine (hips through the head); 90 = arm square to the "
                     "spine, under = arm above the shoulder plane",
        },
        rows=[
            Row("Lead arm vs spine", f"{arm_angle:.0f}°",
                f"{label.lower()} (green {cfg['arm_spine_min']:g}–{cfg['arm_spine_max']:g}°, "
                f"red outside {cfg['arm_spine_watch_min']:g}–{cfg['arm_spine_watch_max']:g}°)", status),
            Row("Top frame", str(f), "marked by you", "ok"),
        ],
        overlays=swing_plane_line(ctx, show) + overlays,
    )
