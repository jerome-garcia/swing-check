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
  hands      the hands should sit straight above the trail heel. Measured
             across the picture, as a share of torso length: + = out toward
             the ball (away from the body), - = behind the heel (deep, flat).

  posture    spine bend kept from address (dtl_body.py, as at the takeaway and
             halfway back): losing it by the top = standing up in the backswing.

Body points come from tracking. Bands are in [analyzers.top]. (A "hands in the
plane zone" check was tried here and dropped at the user's request.)
"""

from __future__ import annotations

import numpy as np

from swingcheck.analyzers import (REFERENCE_COLOR, STATUS_COLORS, MissingData, Overlay, Row, SwingContext, Verdict, grade,
                                  pct, register)
from swingcheck.analyzers.dtl_body import posture_kept, with_body
from swingcheck.analyzers.dtl_swing_plane import swing_plane_line
from swingcheck.geometry import angle_between_deg

HOLD_MS = 400
ORDER = {"ok": 0, "warn": 1, "flag": 2}
HEEL_WINDOW = 3  # frames either side of the top: the heel sits still, so a median steadies it


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
    arm_status = grade(arm_angle, cfg["arm_spine_min"], cfg["arm_spine_max"],
                   cfg["arm_spine_watch_min"], cfg["arm_spine_watch_max"])
    soft = arm_status == "warn"
    if arm_status == "ok":
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

    # Hands vs the trail heel, across the picture.
    forward = -toward_golfer  # screen x direction toward the ball
    heel = ctx.track(ctx.side("heel", "trail"))[max(0, f - HEEL_WINDOW):f + HEEL_WINDOW + 1]
    heel = heel[np.all(np.isfinite(heel), axis=1)]
    heel_xy = np.median(heel, axis=0) if len(heel) else None
    if heel_xy is not None:
        out = ctx.units((hands[0] - heel_xy[0]) * forward)  # + = hands out toward the ball
        heel_status = grade(out, -cfg["heel_max"], cfg["heel_max"], -cfg["heel_watch"], cfg["heel_watch"])
        heel_soft = heel_status == "warn"
        if heel_status == "ok":
            heel_label, heel_meaning, heel_tip = ("Hands over the trail heel",
                                                  "your hands are right above your trail heel", "")
        elif out > 0:
            heel_label = "Hands slightly outside the heel" if heel_soft else "Hands outside the heel"
            heel_meaning = "your hands are out toward the ball, past your trail heel"
            heel_tip = "Turn your shoulders more instead of pushing your hands out toward the ball at the top."
        else:
            heel_label = "Hands slightly behind the heel" if heel_soft else "Hands behind the heel"
            heel_meaning = "your hands are deep behind your trail heel (flat, around the body)"
            heel_tip = "Swing your hands more up than around, so they finish above your trail heel."
        heel_row = Row("Hands vs trail heel", f"{ctx.distance_text(out)} {'toward the ball' if out >= 0 else 'behind'}",
                       f"{pct(abs(out))} of torso length · {heel_label.lower()} "
                       f"(green within ±{pct(cfg['heel_max'])}, red past {pct(cfg['heel_watch'])})", heel_status)
    else:
        out, heel_status, heel_label, heel_meaning, heel_tip = None, "ok", "", "", ""
        heel_row = Row("Hands vs trail heel", "not measured", "trail heel not tracked around the top", "error")

    arm_label = label
    status = max(arm_status, heel_status, key=ORDER.__getitem__)
    if heel_status != "ok":
        label = f"{label}, {heel_label[0].lower() + heel_label[1:]}"
    summary = f"At the top, {meaning}" + (f", and {heel_meaning}." if heel_meaning else ".")
    tip = " ".join(t for t in (tip, heel_tip) if t)

    # Drawing: the spine, the lead arm, and a dashed target arm square to the spine.
    s = ctx.scale
    show = (f, min(len(ctx.pose) - 1, f + int(round(HOLD_MS * ctx.fps / 1000))))
    col = STATUS_COLORS[arm_status]
    spine = head - hip_mid
    square = np.array([-spine[1], spine[0]]) / np.linalg.norm(spine)
    if np.dot(square, hands - lead_shoulder) < 0:
        square = -square
    target = lead_shoulder + square * np.linalg.norm(hands - lead_shoulder)

    # Spine bend kept from address (dtl_body.py). Its lines are drawn only when it's off:
    # the top frame already shows a spine (hips through the head) for the arm check.
    posture = posture_kept(ctx, f, -toward_golfer, show)
    status, label, summary, tip = with_body(status, label, summary, tip, [posture])
    overlays = [
        Overlay("segment", [tuple(hip_mid), tuple(head)], REFERENCE_COLOR, "", show, 2),
        Overlay("segment", [tuple(lead_shoulder), tuple(hands)], col, "", show, 3),
        Overlay("dashed", [tuple(lead_shoulder), tuple(target)], STATUS_COLORS["ok"], "90 deg" if arm_status != "ok" else "",
                show, 2),
        Overlay("point", [tuple(hands)], col, "", show, 2),
        Overlay("point", [tuple(clubhead)], REFERENCE_COLOR, "", show, 1),
        Overlay("text", [(float(lead_shoulder[0]) - toward_golfer * 0.1 * s, float(lead_shoulder[1]) + 0.2 * s)], col,
                f"arm {arm_angle:.0f} deg", show),
    ]
    if heel_xy is not None:
        # A plumb line up from the trail heel past the hands, and the gap to the hands.
        hx, hy = float(heel_xy[0]), float(heel_xy[1])
        heel_col = STATUS_COLORS[heel_status]
        overlays += [
            Overlay("dashed", [(hx, hy), (hx, float(hands[1]) - 0.25 * s)], REFERENCE_COLOR, "trail heel", show, 2),
            Overlay("point", [(hx, hy)], REFERENCE_COLOR, "", show, 1),
            Overlay("segment", [(hx, float(hands[1])), (float(hands[0]), float(hands[1]))], heel_col, "", show, 2),
        ]

    return Verdict(
        status=status,
        label=label,
        summary=summary,
        tip=tip,
        frame=f,
        measurements={
            "arm_to_spine_deg": round(arm_angle, 1),
            "hands_out_from_heel": round(out, 3) if out is not None else None,
            "top_frame": f,
            "units": "degrees between the lead arm and the spine (hips through the head); 90 = arm square to the "
                     "spine, under = arm above the shoulder plane; hands out from heel: share of torso length across the picture, "
                     "+ = toward the ball",
        },
        rows=[
            Row("Lead arm vs spine", f"{arm_angle:.0f}°",
                f"{arm_label.lower()} (green {cfg['arm_spine_min']:g}–{cfg['arm_spine_max']:g}°, "
                f"red outside {cfg['arm_spine_watch_min']:g}–{cfg['arm_spine_watch_max']:g}°)", arm_status),
            heel_row,
            posture.row,
        ],
        overlays=swing_plane_line(ctx, show) + (posture.overlays if posture.status != "ok" else []) + overlays,
    )
