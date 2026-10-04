"""Down-the-line checkpoint 2: swing plane at address.

The line through the clicked clubhead (hosel) and grip is the shaft plane.
Two things are checked on the address frame:

  points at   where that line, extended up past the hands, crosses the
              torso (0% = hip center, 100% = shoulder center). It should point
              roughly at the belt buckle. This is the key check.
  angle       the shaft's angle from horizontal. It varies with the club
              (driver flattest, wedges steepest) and camera height, so it's a
              broad range.

Both have green / yellow / red bands (see [analyzers.swing_plane]).
"""

from __future__ import annotations

import numpy as np

from swingcheck.analyzers import (STATUS_COLORS, MissingData, Overlay, Row, SwingContext, Verdict, grade,
                                  pct, register)

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


def swing_plane_line(ctx: SwingContext, show: tuple[int, int] | None) -> list[Overlay]:
    """The swing plane line (the address shaft line, clubhead through grip) across the
    whole frame, labeled. Every checkpoint from 2 to 8 draws it on its key frame, so the
    clubhead can be judged against it by eye."""
    pts = ctx.marks.points
    ch0, gr0 = np.asarray(pts["clubhead"], float), np.asarray(pts["grip"], float)
    if np.linalg.norm(gr0 - ch0) < 1:
        return []
    return [Overlay("line", [tuple(ch0), tuple(gr0)], PLANE_COLOR, "swing plane", show, 2)]


@register("swing_plane", view="dtl", title="Swing plane", phase="address")
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

    # aim: short result (headline and frame label); aim_note: what it means.
    aim_status = grade(u, cfg["belt_min"], cfg["belt_max"], cfg["belt_watch_min"], cfg["belt_watch_max"])
    if aim_status != "ok" and u < cfg["belt_min"]:
        if aim_status == "warn":
            aim, aim_note = "Points just below belt", "Shaft slightly flat: maybe standing a bit far from the ball or hands a bit low."
        else:
            aim, aim_note = "Points below belt", "Shaft too flat: likely standing too far from the ball or hands too low."
    elif aim_status != "ok":
        if aim_status == "warn":
            aim, aim_note = "Points just above belt", "Shaft slightly upright: maybe standing a bit close to the ball or hands a bit high."
        else:
            aim, aim_note = "Points above belt", "Shaft too upright: likely standing too close to the ball or hands too high."
    else:
        aim, aim_note = "Points at belt buckle", "Shaft is well aligned with your body."

    angle_status = grade(angle, cfg["angle_min"], cfg["angle_max"], cfg["angle_watch_min"], cfg["angle_watch_max"])
    angle_ok = angle_status == "ok"
    angle_text = "in range" if angle_ok else (
        ("slightly " if angle_status == "warn" else "") + ("flat" if angle < cfg["angle_min"] else "steep"))

    order = {"ok": 0, "warn": 1, "flag": 2}
    status = max(aim_status, angle_status, key=order.__getitem__)
    label = aim + ("" if angle_ok else f", angle {angle:.0f}° ({angle_text})")
    summary = aim_note
    if not angle_ok:
        summary += (f" Shaft angle {angle:.0f}° is outside {cfg['angle_min']}-{cfg['angle_max']}°"
                    " (check the club and camera height).")

    # Drawing: the swing plane line across the whole frame, kept on screen for the whole
    # video so the clubhead can be followed against it; plus the belt-buckle zone on the
    # torso, where the line crosses it, and the result.
    s = ctx.scale
    t = shoulder - hip
    cross = hip + u * t
    zone = [tuple(hip + cfg["belt_min"] * t), tuple(hip + cfg["belt_max"] * t)]
    show = (0, max(f, ctx.frame("takeaway")))
    color = STATUS_COLORS[status]
    overlays = swing_plane_line(ctx, (0, len(ctx.pose) - 1)) + [
        Overlay("segment", zone, ZONE_COLOR, "", show, 6),
        Overlay("point", [tuple(cross)], color, "", show, 2),
        Overlay("text", [(float(cross[0]) + 0.12 * s, float(cross[1]))], color, aim, show),
    ]
    tips = []
    if aim_status != "ok":
        tips.append("Stand a touch closer to the ball or raise your hands slightly, so the shaft points at your belt buckle."
                    if u < cfg["belt_min"] else
                    "Stand a touch farther from the ball or let your hands hang lower, so the shaft points at your belt buckle.")
    if angle_status != "ok":
        tips.append("Check the club and the camera height (about hand height) before changing your setup.")
    fix_tip = " ".join(tips)

    return Verdict(
        status=status,
        label=label,
        summary=summary,
        tip=fix_tip,
        measurements={
            "shaft_angle_deg": round(angle, 1),
            "angle": angle_text,
            "alignment": f"{aim}. {aim_note}",
            "crosses_torso_at": round(u, 2),
            "units": "crosses torso at: share of the way from hip center (0) to shoulder center (1); "
                     f"the belt buckle is {cfg['belt_min']:g}-{cfg['belt_max']:g}",
        },
        overlays=overlays,
        rows=[
            Row("Alignment", f"{pct(u)} up the torso",
                f"{ctx.distance_text(u)} {'above' if u >= 0 else 'below'} hip center · {aim} "
                f"(green {pct(cfg['belt_min'])}–{pct(cfg['belt_max'])}, "
                f"red below {pct(cfg['belt_watch_min'])} or above {pct(cfg['belt_watch_max'])})", aim_status),
            Row("Shaft angle", f"{angle:.1f}°",
                f"{angle_text} (green {cfg['angle_min']:g}–{cfg['angle_max']:g}°, "
                f"red outside {cfg['angle_watch_min']:g}–{cfg['angle_watch_max']:g}°)", angle_status),
        ],
    )
