"""Down-the-line checkpoint 2: swing plane at address.

The line through the clicked clubhead (hosel) and grip is the shaft plane.
Two things are checked on the address frame:

  points at   where that line, extended up past the hands, crosses the
              torso (0 = hip center, 1 = shoulder center). It should point
              roughly at the belt buckle. This is the key check.
  angle       the shaft's angle from horizontal. It varies with the club
              (driver flattest, wedges steepest) and camera height, so it's
              only a broad sanity range.
"""

from __future__ import annotations

import numpy as np

from swingcheck.analyzers import REFERENCE_COLOR, STATUS_COLORS, MissingData, Overlay, SwingContext, Verdict, register

PLANE_COLOR = (0, 140, 255)  # orange, like the classic drawn-on shaft line
ZONE_COLOR = (80, 200, 80)


def shaft_angle_deg(clubhead, grip) -> float:
    """Angle of the clubhead->grip line above horizontal, 0-90 degrees (image y grows down)."""
    d = np.asarray(grip, float) - np.asarray(clubhead, float)
    return float(np.degrees(np.arctan2(-d[1], abs(d[0]))))


def torso_crossing(clubhead, grip, hip, shoulder) -> float:
    """Where the extended shaft line crosses the hip->shoulder line, as a fraction of it
    (0 = hip, 1 = shoulder; outside 0-1 means below the hips or above the shoulders)."""
    c, g, h, s = (np.asarray(p, float) for p in (clubhead, grip, hip, shoulder))
    d, t = g - c, s - h
    m = np.array([[d[0], -t[0]], [d[1], -t[1]]])
    if abs(np.linalg.det(m)) < 1e-6 * np.linalg.norm(d) * np.linalg.norm(t):
        raise MissingData("the shaft line runs parallel to the spine, so it never points at the body")
    _, u = np.linalg.solve(m, h - c)
    return float(u)


@register("swing_plane", view="dtl", title="Swing plane")
def swing_plane(ctx: SwingContext) -> Verdict:
    cfg = ctx.cfg
    f = ctx.marks.address_frame
    pts = ctx.marks.points
    clubhead, grip = np.asarray(pts["clubhead"], float), np.asarray(pts["grip"], float)
    if np.linalg.norm(grip - clubhead) < 5:
        raise MissingData("the clubhead and grip marks are on top of each other; re-mark them")

    hip = ctx.midpoint("left_hip", "right_hip")[f]
    shoulder = ctx.midpoint("left_shoulder", "right_shoulder")[f]
    if not (np.all(np.isfinite(hip)) and np.all(np.isfinite(shoulder))):
        hip = ctx.value(ctx.track(ctx.side("hip", "trail")), f, "trail hip")
        shoulder = ctx.value(ctx.track(ctx.side("shoulder", "trail")), f, "trail shoulder")

    angle = shaft_angle_deg(clubhead, grip)
    u = torso_crossing(clubhead, grip, hip, shoulder)

    if u < cfg["belt_min"]:
        aim_status, aim = "flag", "below the belt"
        aim_note = "Shaft too flat: likely standing too far from the ball or hands too low."
    elif u > cfg["belt_max"]:
        aim_status, aim = "flag", "above the belt"
        aim_note = "Shaft too upright: likely standing too close to the ball or hands too high."
    else:
        aim_status, aim, aim_note = "ok", "at the belt buckle", "Shaft line points at the belt buckle."

    angle_ok = cfg["angle_min"] <= angle <= cfg["angle_max"]
    angle_text = "in range" if angle_ok else ("flat" if angle < cfg["angle_min"] else "steep")

    status = aim_status if aim_status == "flag" else ("ok" if angle_ok else "warn")
    label = f"points {aim}" + ("" if angle_ok else f", angle {angle:.0f}° ({angle_text})")
    summary = aim_note
    if not angle_ok:
        summary += (f" Shaft angle {angle:.0f}° is outside {cfg['angle_min']}-{cfg['angle_max']}°"
                    " (check the club and camera height).")

    # Drawing: the shaft line extended up to (a bit past) where it meets the torso,
    # the belt-buckle target zone on the torso line, and a horizontal reference at the clubhead.
    s = ctx.scale
    t = shoulder - hip
    cross = hip + u * t
    direction = (grip - clubhead) / np.linalg.norm(grip - clubhead)
    reach = max(np.dot(cross - clubhead, direction), np.linalg.norm(grip - clubhead)) + 0.15 * s
    tip = clubhead + direction * reach
    zone = [tuple(hip + cfg["belt_min"] * t), tuple(hip + cfg["belt_max"] * t)]
    toward_golfer = 1.0 if grip[0] < clubhead[0] else -1.0
    show = (0, max(f, ctx.frame("takeaway")))
    color = STATUS_COLORS[status]
    overlays = [
        Overlay("segment", zone, ZONE_COLOR, "", show, 6),
        Overlay("segment", [tuple(hip), tuple(shoulder)], REFERENCE_COLOR, "", show, 1),
        Overlay("segment", [tuple(clubhead), tuple(tip)], PLANE_COLOR, "", show, 3),
        Overlay("segment", [tuple(clubhead), (clubhead[0] - toward_golfer * 0.35 * s, clubhead[1])], REFERENCE_COLOR, "", show, 1),
        Overlay("point", [tuple(cross)], color, "", show, 2),
        Overlay("text", [(float(cross[0]) + 0.12 * s, float(cross[1]))], color, f"points {aim}", show),
        Overlay("text", [tuple((clubhead + grip) / 2 - np.array([toward_golfer * 0.1 * s, 0.0]))],
                PLANE_COLOR, f"plane {angle:.0f} deg", show),
    ]
    return Verdict(
        status=status,
        label=label,
        summary=summary,
        measurements={
            "shaft_angle_deg": round(angle, 1),
            "angle": angle_text,
            "points_at": aim.removeprefix("at "),
            "crosses_torso_at": round(u, 2),
            "units": "crosses torso at: 0 = hip, 1 = shoulder; the belt buckle is "
                     f"{cfg['belt_min']:g}-{cfg['belt_max']:g}",
        },
        overlays=overlays,
    )
