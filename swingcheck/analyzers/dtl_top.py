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

from swingcheck.analyzers import (MissingData, Overlay, REFERENCE_COLOR, Row, STATUS_COLORS, SwingContext, Verdict,
                                  clubhead_mark, deg_text, grade, hands_mark, register, spot_mark, WATCH_ONLY, watch_at_most)
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
        raise MissingData("The top isn't marked yet. Go to Edit marks → Top and click the clubhead and hands.")
    cfg = ctx.cfg
    f = mark.frame
    clubhead = np.asarray(mark.points["clubhead"], float)
    hands = np.asarray(mark.points["grip"], float)
    ball = np.asarray(ctx.marks.points["ball"], float)

    hip0 = ctx.midpoint("left_hip", "right_hip")[ctx.marks.address_frame]
    if not np.all(np.isfinite(hip0)):
        hip0 = ctx.value(ctx.track(ctx.side("hip", "trail")), ctx.marks.address_frame, "back hip")
    toward_golfer = -1.0 if hip0[0] < ball[0] else 1.0

    # Lead arm vs spine on the top frame.
    lead_shoulder = ctx.value(ctx.track(ctx.side("shoulder", "lead")), f, "front shoulder")
    hip_mid = ctx.midpoint("left_hip", "right_hip")[f]
    # Spine: hip center through the head (between the ears; the nose if the ears are lost).
    head = ctx.midpoint("left_ear", "right_ear")[f]
    if not np.all(np.isfinite(head)):
        head = ctx.track("nose")[f]
    if not (np.all(np.isfinite(head)) and np.all(np.isfinite(hip_mid))):
        raise MissingData(f"Your head or hips weren't tracked on the top frame ({f}).")
    arm_angle = angle_between_deg(hands - lead_shoulder, head - hip_mid)
    arm_status = grade(arm_angle, cfg["arm_spine_min"], cfg["arm_spine_max"],
                   cfg["arm_spine_watch_min"], cfg["arm_spine_watch_max"])
    soft = arm_status == "warn"
    if arm_status == "ok":
        label, meaning = ("Front arm matches your shoulders",
                          "your front (lead) arm is square to your spine, in line with your shoulders")
        tip = ""
    elif arm_angle < cfg["arm_spine_min"]:
        label = "Front arm slightly above your shoulders" if soft else "Front arm above your shoulders"
        meaning = "your front (lead) arm is lifted above your shoulder line (upright)"
        tip = "Turn your shoulders more and keep your front arm across your chest instead of lifting it."
    else:
        label = "Front arm slightly below your shoulders" if soft else "Front arm below your shoulders"
        meaning = "your front (lead) arm is below your shoulder line (flat, around your body)"
        tip = "Swing your front arm a little higher so it matches your shoulder turn."

    # Hands vs the trail heel, across the picture.
    forward = -toward_golfer  # screen x direction toward the ball
    heel = ctx.track(ctx.side("heel", "trail"))[max(0, f - HEEL_WINDOW):f + HEEL_WINDOW + 1]
    heel = heel[np.all(np.isfinite(heel), axis=1)]
    heel_xy = np.median(heel, axis=0) if len(heel) else None
    if heel_xy is not None:
        out = ctx.units((hands[0] - heel_xy[0]) * forward)  # + = hands out toward the ball
        # Watch at most: deep or shallow hands at the top vary with the club (a driver is
        # flatter) and the camera angle, and rarely cost a shot by themselves.
        heel_band = grade(out, -cfg["heel_max"], cfg["heel_max"], -cfg["heel_watch"], cfg["heel_watch"])
        heel_soft = heel_band == "warn"
        heel_status = watch_at_most(heel_band)
        if heel_status == "ok":
            heel_label, heel_meaning, heel_tip = ("Hands over your back heel",
                                                  "your hands are right above your back (trail) heel", "")
        elif out > 0:
            heel_label = "Hands slightly toward the ball" if heel_soft else "Hands too far toward the ball"
            heel_meaning = "your hands are out toward the ball, past your back heel"
            heel_tip = "Turn your shoulders more instead of pushing your hands out toward the ball at the top."
        else:
            heel_label = "Hands slightly behind your back heel" if heel_soft else "Hands behind your back heel"
            heel_meaning = "your hands are deep behind your back heel (flat, around the body)"
            heel_tip = "Swing your hands more up than around, so they finish above your back heel."
        heel_value = ("Right above it" if abs(ctx.cm(out)) < 0.75 else
                      f"{ctx.distance_text(out)} {'toward the ball' if out >= 0 else 'behind'}")
        heel_row = Row("Hands vs back heel", heel_value, heel_label.removeprefix("Hands ").capitalize(), heel_status,
                       good=f"within {ctx.distance_text(cfg['heel_max'])} of your heel", fix=WATCH_ONLY)
    else:
        out, heel_status, heel_label, heel_meaning, heel_tip = None, "ok", "", "", ""
        heel_row = Row("Hands vs back heel", "Not measured", "Back heel not tracked around the top", "error")

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
        Overlay("dashed", [tuple(lead_shoulder), tuple(target)], REFERENCE_COLOR, "Target 90 deg" if arm_status != "ok" else "",
                show, 2),
        hands_mark(hands, col, show),
        clubhead_mark(clubhead, REFERENCE_COLOR, show),  # shown, not measured here
        Overlay("text", [(float(lead_shoulder[0]) - toward_golfer * 0.1 * s, float(lead_shoulder[1]) + 0.2 * s)], col,
                f"Arm {arm_angle:.0f} deg", show),
    ]
    if heel_xy is not None:
        # A plumb line up from the trail heel past the hands, and the gap to the hands.
        hx, hy = float(heel_xy[0]), float(heel_xy[1])
        heel_col = STATUS_COLORS[heel_status]
        overlays += [
            Overlay("dashed", [(hx, hy), (hx, float(hands[1]) - 0.25 * s)], REFERENCE_COLOR, "Back heel", show, 2),
            spot_mark((hx, hy), REFERENCE_COLOR, show),
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
            Row("Front arm vs spine", deg_text(arm_angle), arm_label.removeprefix("Front arm ").capitalize(),
                arm_status, good=f"{cfg['arm_spine_min']:g}–{cfg['arm_spine_max']:g}° (about square)",
                fix=f"under {cfg['arm_spine_watch_min']:g}° or over {cfg['arm_spine_watch_max']:g}°"),
            heel_row,
            posture.row,
        ],
        overlays=swing_plane_line(ctx, show) + (posture.overlays if posture.status != "ok" else []) + overlays,
    )
