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

from swingcheck.analyzers import (MissingData, Overlay, PLANE_BAND_COLOR, PLANE_COLOR, REFERENCE_COLOR, Row,
                                  STATUS_COLORS, SwingContext, Verdict, deg_text, grade, register, spot_mark)



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
        raise MissingData("The shaft line runs parallel to your spine, so it never points at your body.")
    _, u = np.linalg.solve(m, h - c)
    return float(u)




def swing_plane_line(ctx: SwingContext, show: tuple[int, int] | None) -> list[Overlay]:
    """The swing plane line (the address shaft line, clubhead through grip) across the
    whole frame, labeled, with a grey boundary line either side marking the on-plane
    corridor (the takeaway's green band, [analyzers.takeaway] line_tolerance). Every
    checkpoint from 2 to 8 draws it on its key frame, so the clubhead can be judged
    against it by eye."""
    pts = ctx.marks.points
    ch0, gr0 = np.asarray(pts["clubhead"], float), np.asarray(pts["grip"], float)
    if np.linalg.norm(gr0 - ch0) < 1:
        return []
    d = (gr0 - ch0) / np.linalg.norm(gr0 - ch0)
    off = np.array([-d[1], d[0]]) * ctx.config["analyzers"]["takeaway"]["line_tolerance"] * ctx.scale
    return [Overlay("line", [tuple(ch0 + off), tuple(gr0 + off)], PLANE_BAND_COLOR, "", show, 1),
            Overlay("line", [tuple(ch0 - off), tuple(gr0 - off)], PLANE_BAND_COLOR, "", show, 1),
            Overlay("line", [tuple(ch0), tuple(gr0)], PLANE_COLOR, "Swing plane", show, 2)]


@register("swing_plane", view="dtl", title="Swing plane", phase="address")
def swing_plane(ctx: SwingContext) -> Verdict:
    cfg = ctx.cfg
    f = ctx.marks.address_frame
    pts = ctx.marks.points
    clubhead, grip = np.asarray(pts["clubhead"], float), np.asarray(pts["grip"], float)
    if np.linalg.norm(grip - clubhead) < 5:
        raise MissingData("The clubhead and hands marks are on top of each other. Mark them again.")

    hip = ctx.midpoint("left_hip", "right_hip")[f]
    shoulder = ctx.midpoint("left_shoulder", "right_shoulder")[f]
    if not (np.all(np.isfinite(hip)) and np.all(np.isfinite(shoulder))):
        hip = ctx.value(ctx.track(ctx.side("hip", "trail")), f, "back hip")
        shoulder = ctx.value(ctx.track(ctx.side("shoulder", "trail")), f, "back shoulder")

    angle = shaft_angle_deg(clubhead, grip)
    u = torso_crossing(clubhead, grip, hip, shoulder)

    # aim: short result (headline and frame label); aim_note: what it means.
    aim_status = grade(u, cfg["belt_min"], cfg["belt_max"], cfg["belt_watch_min"], cfg["belt_watch_max"])
    if aim_status != "ok" and u < cfg["belt_min"]:
        if aim_status == "warn":
            aim, aim_note = ("Points just below your belt",
                             "The shaft is a little flat: you may be standing a bit far from the ball, or your hands are a bit low.")
        else:
            aim, aim_note = ("Points below your belt",
                             "The shaft is too flat: you're likely standing too far from the ball, or your hands are too low.")
    elif aim_status != "ok":
        if aim_status == "warn":
            aim, aim_note = ("Points just above your belt",
                             "The shaft is a little upright: you may be standing a bit close to the ball, or your hands are a bit high.")
        else:
            aim, aim_note = ("Points above your belt",
                             "The shaft is too upright: you're likely standing too close to the ball, or your hands are too high.")
    else:
        aim, aim_note = "Points at your belt buckle", "At address, the club shaft points at your belt buckle."

    angle_status = grade(angle, cfg["angle_min"], cfg["angle_max"], cfg["angle_watch_min"], cfg["angle_watch_max"])
    angle_ok = angle_status == "ok"
    angle_text = "In range" if angle_ok else (
        ("Slightly " if angle_status == "warn" else "Too ") + ("flat" if angle < cfg["angle_min"] else "steep"))

    order = {"ok": 0, "warn": 1, "flag": 2}
    status = max(aim_status, angle_status, key=order.__getitem__)
    label = aim + ("" if angle_ok else f", shaft {angle_text.lower()}")
    summary = aim_note
    if not angle_ok:
        summary += (f" The shaft sits at {deg_text(angle)} from the ground, outside the usual "
                    f"{cfg['angle_min']:g}–{cfg['angle_max']:g}°.")

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
        Overlay("segment", zone, REFERENCE_COLOR, "", show, 6),  # the target
        spot_mark(cross, color, show),
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
            Row("Shaft points at", f"{ctx.distance_text(u)} {'above' if u >= 0 else 'below'} your hips",
                aim.removeprefix("Points ").capitalize(), aim_status,
                good=f"your hips to {ctx.distance_text(cfg['belt_max'])} above (belt buckle)",
                fix=f"more than {ctx.distance_text(cfg['belt_watch_min'])} below or "
                    f"{ctx.distance_text(cfg['belt_watch_max'])} above your hips"),
            Row("Shaft angle", deg_text(angle), angle_text, angle_status,
                good=f"{cfg['angle_min']:g}–{cfg['angle_max']:g}° from the ground",
                fix=f"under {cfg['angle_watch_min']:g}° or over {cfg['angle_watch_max']:g}°"),
        ],
    )
