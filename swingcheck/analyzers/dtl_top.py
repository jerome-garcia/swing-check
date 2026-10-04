"""Down-the-line checkpoint 5: top of the backswing.

On the top frame you mark, using the clubhead and hands you click there:

  lead arm   the lead arm (lead shoulder -> hands) should match the shoulders:
             about 90° to the spine (hip center -> shoulder center). Under 90°
             = arm above the shoulder plane (lifted, upright); over 90° = below
             it (flat, around the body).
  plane      the hands should sit between two lines from the ball (Hogan's
             "pane of glass"): the address shaft line (lower, checkpoint 2) and
             the line from the ball to your trail shoulder at address (upper).
             Above the upper line = too steep; below the lower line = too flat.

Body points come from tracking. Bands are in [analyzers.top].
"""

from __future__ import annotations

import numpy as np

from swingcheck.analyzers import (REFERENCE_COLOR, STATUS_COLORS, MissingData, Overlay, Row, SwingContext, Verdict, grade,
                                  pct, register)
from swingcheck.geometry import angle_between_deg

PLANE_COLOR = (0, 140, 255)  # address shaft line, as in checkpoint 2
UPPER_COLOR = (255, 200, 80)  # ball -> trail shoulder line
HOLD_MS = 400
ORDER = {"ok": 0, "warn": 1, "flag": 2}


def _x_at(p: np.ndarray, q: np.ndarray, y: float) -> float:
    """Screen x of the line through p and q at height y."""
    if abs(q[1] - p[1]) < 1e-6:
        raise MissingData("a plane line is level in the image")
    return float(p[0] + (y - p[1]) * (q[0] - p[0]) / (q[1] - p[1]))


@register("top", view="dtl", title="Top", phase="top")
def top(ctx: SwingContext) -> Verdict:
    mark = ctx.marks.checkpoint("top")
    if mark is None:
        raise MissingData("the top isn't marked yet: Edit marks → Top, then click the clubhead and hands")
    cfg = ctx.cfg
    f = mark.frame
    a = ctx.marks.address_frame
    clubhead = np.asarray(mark.points["clubhead"], float)
    hands = np.asarray(mark.points["grip"], float)
    pts = ctx.marks.points
    ball = np.asarray(pts["ball"], float)
    ch0, gr0 = np.asarray(pts["clubhead"], float), np.asarray(pts["grip"], float)

    hip0 = ctx.midpoint("left_hip", "right_hip")[a]
    if not np.all(np.isfinite(hip0)):
        hip0 = ctx.value(ctx.track(ctx.side("hip", "trail")), a, "trail hip")
    toward_golfer = -1.0 if hip0[0] < ball[0] else 1.0

    # 1. Lead arm vs spine on the top frame.
    lead_shoulder = ctx.value(ctx.track(ctx.side("shoulder", "lead")), f, "lead shoulder")
    sh_mid = ctx.midpoint("left_shoulder", "right_shoulder")[f]
    hip_mid = ctx.midpoint("left_hip", "right_hip")[f]
    if not (np.all(np.isfinite(sh_mid)) and np.all(np.isfinite(hip_mid))):
        raise MissingData(f"shoulders or hips not tracked on the top frame ({f})")
    arm_angle = angle_between_deg(hands - lead_shoulder, sh_mid - hip_mid)
    arm_status = grade(arm_angle, cfg["arm_spine_min"], cfg["arm_spine_max"],
                       cfg["arm_spine_watch_min"], cfg["arm_spine_watch_max"])
    soft = arm_status == "warn"
    if arm_status == "ok":
        arm_label, arm_meaning = "Lead arm matches the shoulders", "your lead arm is square to your spine, on the shoulder plane"
    elif arm_angle < cfg["arm_spine_min"]:
        arm_label = "Lead arm slightly above the shoulders" if soft else "Lead arm above the shoulders"
        arm_meaning = "your lead arm is lifted above the shoulder plane (upright)"
    else:
        arm_label = "Lead arm slightly below the shoulders" if soft else "Lead arm below the shoulders"
        arm_meaning = "your lead arm is below the shoulder plane (flat, around your body)"

    # 2. Hands between the address shaft line and the ball -> trail shoulder line, across at the hands' height.
    trail_shoulder0 = ctx.value(ctx.track(ctx.side("shoulder", "trail")), a, "trail shoulder at address")
    x_lower = _x_at(ch0, gr0, hands[1])
    x_upper = _x_at(ball, trail_shoulder0, hands[1])
    # Distances toward the ball side (away from the golfer) are "above" the plane in this view.
    above_upper = ctx.units((hands[0] - x_upper) * -toward_golfer)  # > 0: past the upper line
    below_lower = ctx.units((x_lower - hands[0]) * -toward_golfer)  # > 0: past the lower line
    outside = max(above_upper, below_lower, 0.0)
    plane_status = "ok" if outside == 0 else ("warn" if outside <= cfg["plane_watch"] else "flag")
    soft = plane_status == "warn"
    if plane_status == "ok":
        plane_label, plane_meaning = "Hands on plane", "your hands are between the plane lines"
        plane_value = "between the lines"
    elif above_upper > 0:
        plane_label = "Hands slightly above the plane" if soft else "Hands above the plane"
        plane_meaning = "your hands are above the upper plane line (steep / upright)"
        plane_value = f"{ctx.distance_text(above_upper)} above"
    else:
        plane_label = "Hands slightly below the plane" if soft else "Hands below the plane"
        plane_meaning = "your hands are below the address shaft line (flat / around)"
        plane_value = f"{ctx.distance_text(below_lower)} below"

    status = max(arm_status, plane_status, key=ORDER.__getitem__)
    label = f"{arm_label}, {plane_label[0].lower() + plane_label[1:]}"
    summary = f"At the top, {arm_meaning}, and {plane_meaning}."

    # Drawing: both plane lines up past the hands, the spine, the lead arm, and a dashed
    # target arm square to the spine.
    s = ctx.scale
    show = (f, min(len(ctx.pose) - 1, f + int(round(HOLD_MS * ctx.fps / 1000))))
    arm_col, plane_col = STATUS_COLORS[arm_status], STATUS_COLORS[plane_status]
    reach_y = hands[1] - 0.3 * s

    def up_to(p, q):
        return (_x_at(p, q, reach_y), reach_y)

    spine = sh_mid - hip_mid
    square = np.array([-spine[1], spine[0]]) / np.linalg.norm(spine)
    if np.dot(square, hands - lead_shoulder) < 0:
        square = -square
    target = lead_shoulder + square * np.linalg.norm(hands - lead_shoulder)
    overlays = [
        Overlay("segment", [tuple(ch0), up_to(ch0, gr0)], PLANE_COLOR, "", show, 2),
        Overlay("segment", [tuple(ball), up_to(ball, trail_shoulder0)], UPPER_COLOR, "", show, 2),
        Overlay("segment", [tuple(hip_mid), tuple(sh_mid)], REFERENCE_COLOR, "", show, 2),
        Overlay("segment", [tuple(lead_shoulder), tuple(hands)], arm_col, "", show, 3),
        Overlay("dashed", [tuple(lead_shoulder), tuple(target)], STATUS_COLORS["ok"], "90 deg" if arm_status != "ok" else "",
                show, 2),
        Overlay("point", [tuple(hands)], plane_col, "", show, 2),
        Overlay("point", [tuple(clubhead)], REFERENCE_COLOR, "", show, 1),
        Overlay("text", [(float(lead_shoulder[0]) - toward_golfer * 0.1 * s, float(lead_shoulder[1]) + 0.2 * s)], arm_col,
                f"arm {arm_angle:.0f} deg", show),
        Overlay("text", [(float(hands[0]) - toward_golfer * 0.15 * s, float(hands[1]) - 0.2 * s)], plane_col, plane_label, show),
    ]

    tips = []
    if arm_status != "ok":
        tips.append("Turn your shoulders more and keep the lead arm across your chest instead of lifting it."
                    if arm_angle < cfg["arm_spine_min"] else
                    "Swing the lead arm a little higher so it matches your shoulder turn.")
    if plane_status != "ok":
        tips.append("Less arm lift at the top: let the shoulder turn carry the club." if above_upper > 0 else
                    "Swing the hands a little higher, less around your body.")
    tip = " ".join(tips)

    return Verdict(
        status=status,
        label=label,
        summary=summary,
        tip=tip,
        frame=f,
        measurements={
            "arm_to_spine_deg": round(arm_angle, 1),
            "hands_above_upper_line": round(above_upper, 3),
            "hands_below_lower_line": round(below_lower, 3),
            "top_frame": f,
            "units": "angle in degrees (90 = arm square to the spine; under = arm above the shoulder plane); "
                     "plane distances as a share of torso length, > 0 = outside that line",
        },
        rows=[
            Row("Lead arm vs spine", f"{arm_angle:.0f}°",
                f"{arm_label.lower()} (green {cfg['arm_spine_min']:g}–{cfg['arm_spine_max']:g}°, "
                f"red outside {cfg['arm_spine_watch_min']:g}–{cfg['arm_spine_watch_max']:g}°)", arm_status),
            Row("Hands vs plane", plane_value,
                (f"{pct(outside)} of torso length · " if outside else "") +
                f"{plane_label.lower()} (green between the lines, red past {pct(cfg['plane_watch'])} outside)",
                plane_status),
            Row("Top frame", str(f), "marked by you", "ok"),
        ],
        overlays=overlays,
    )
