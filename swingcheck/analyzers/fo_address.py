"""Face-on checkpoint 1: address.

On the address frame you mark, with the ball you click there:

  stance width   the distance between the ankles over the distance between the shoulder
                 joints. Too narrow costs balance; too wide stops the hips turning. A
                 driver wants a wider stance than an iron.
  ball position  where the ball sits between the ankles: 0 = back ankle, 1 = front ankle.
                 With irons it moves back as the club gets shorter (a wedge in the middle,
                 a long iron ahead of it), so only the extremes count. A driver goes
                 forward, about level with the inside of the front heel.
  spine tilt     the line from the hip center to the shoulder center against vertical;
                 + = tilted away from the target (the trail shoulder lower), as it should
                 be. Leaning toward the target sets up a steep, downward hit.

Bands are in [analyzers.fo_address] (driver ones in [clubs.driver.analyzers.fo_address]).
"""

from __future__ import annotations

import numpy as np

from swingcheck.analyzers import (MissingData, Overlay, REFERENCE_COLOR, Row, STATUS_COLORS, SwingContext, Verdict,
                                  deg_text, grade, register, spot_mark)

ORDER = {"ok": 0, "warn": 1, "flag": 2}


def _at(track: np.ndarray, frame: int, what: str) -> np.ndarray:
    xy = track[frame]
    if not np.all(np.isfinite(xy)):
        raise MissingData(f"Your {what} wasn't tracked on the address frame.")
    return xy


def _range(lo: float, hi: float, fmt) -> str:
    return f"{fmt(lo)} to {fmt(hi)}"


@register("fo_address", view="fo", title="Address", phase="address")
def fo_address(ctx: SwingContext) -> Verdict:
    cfg = ctx.cfg
    sign = ctx.target_sign  # +1: the target is screen-right
    a = ctx.marks.address_frame
    lead, trail = ctx.side("ankle", "lead"), ctx.side("ankle", "trail")
    lead_ankle = _at(ctx.track(lead), a, "front ankle")
    trail_ankle = _at(ctx.track(trail), a, "back ankle")
    shoulders = [_at(ctx.track(n), a, "shoulders") for n in ("left_shoulder", "right_shoulder")]
    hips = _at(ctx.midpoint("left_hip", "right_hip"), a, "hips")
    sh_mid = (shoulders[0] + shoulders[1]) / 2
    ball = np.asarray(ctx.marks.points["ball"], float)

    # 1. Stance width, as a multiple of shoulder width.
    shoulder_w = abs(shoulders[0][0] - shoulders[1][0])
    if shoulder_w <= 0:
        raise MissingData("Couldn't measure your shoulders on the address frame.")
    stance = abs(lead_ankle[0] - trail_ankle[0]) / shoulder_w
    stance_status = grade(stance, cfg["stance_min"], cfg["stance_max"], cfg["stance_watch_min"], cfg["stance_watch_max"])
    if stance_status == "ok":
        stance_label, stance_meaning = "Good stance width", "your feet are a good width apart"
    elif stance < cfg["stance_min"]:
        stance_label = "Stance slightly narrow" if stance_status == "warn" else "Stance too narrow"
        stance_meaning = "your feet are close together, which costs balance"
    else:
        stance_label = "Stance slightly wide" if stance_status == "warn" else "Stance too wide"
        stance_meaning = "your feet are wide apart, which makes it hard to turn your hips"

    # 2. Ball position between the ankles: 0 = back ankle, 1 = front ankle.
    span = (lead_ankle[0] - trail_ankle[0]) * sign
    if span <= 0:
        raise MissingData("Couldn't tell your front foot from your back foot on the address frame.")
    position = (ball[0] - trail_ankle[0]) * sign / span
    ball_status = grade(position, cfg["ball_min"], cfg["ball_max"], cfg["ball_watch_min"], cfg["ball_watch_max"])
    if ball_status == "ok":
        ball_label, ball_meaning = "Ball well placed", "the ball is in a good place in your stance"
    elif position < cfg["ball_min"]:
        ball_label = "Ball slightly back" if ball_status == "warn" else "Ball too far back"
        ball_meaning = "the ball sits back in your stance, toward your back foot"
    else:
        ball_label = "Ball slightly forward" if ball_status == "warn" else "Ball too far forward"
        ball_meaning = "the ball sits forward in your stance, toward your front foot"

    # 3. Spine tilt: + = away from the target.
    v = sh_mid - hips
    tilt = float(np.degrees(np.arctan2(-v[0] * sign, -v[1])))
    tilt_status = grade(tilt, cfg["tilt_min"], cfg["tilt_max"], cfg["tilt_watch_min"], cfg["tilt_watch_max"])
    if tilt_status == "ok":
        tilt_label, tilt_meaning = "Spine tilted slightly away", "your spine tilts slightly away from the target"
    elif tilt < cfg["tilt_min"]:
        tilt_label = "Leaning slightly toward the target" if tilt_status == "warn" else "Leaning toward the target"
        tilt_meaning = "your upper body leans toward the target"
    else:
        tilt_label = "Tilted far away" if tilt_status == "flag" else "Tilted a lot away"
        tilt_meaning = "your upper body tilts a lot away from the target"

    status = max(stance_status, ball_status, tilt_status, key=ORDER.__getitem__)
    label = ("Good setup from the front" if status == "ok" else
             next(lab for st, lab in ((stance_status, stance_label), (ball_status, ball_label), (tilt_status, tilt_label))
                  if st == status))
    summary = f"At address, {stance_meaning}, {ball_meaning}, and {tilt_meaning}."

    tips = []
    if stance_status != "ok":
        tips.append("Set your feet so the insides of your heels are about as wide as your shoulders (a little wider "
                    "with a driver)." if stance < cfg["stance_min"] else
                    "Bring your feet in a little, to about shoulder width (a little wider with a driver).")
    if ball_status != "ok":
        tips.append("Move the ball forward, toward the middle of your stance." if position < cfg["ball_min"] else
                    "Move the ball back, toward the middle of your stance (inside your front heel with a driver).")
    if tilt_status != "ok":
        tips.append("Let your back shoulder sit a little lower than your front one, so your spine tilts slightly "
                    "away from the target." if tilt < cfg["tilt_min"] else
                    "Stand a little taller over the ball: your spine only needs a slight tilt away from the target.")

    # Drawing on the address frame: lines up from each ankle and the ball, the shoulder
    # line, and the spine against a vertical.
    s = ctx.scale
    show = (a, a)
    stance_col, ball_col, tilt_col = (STATUS_COLORS[x] for x in (stance_status, ball_status, tilt_status))
    foot_top = float(min(lead_ankle[1], trail_ankle[1]) - 0.5 * s)
    overlays = [
        Overlay("vline", [(float(trail_ankle[0]), foot_top), tuple(trail_ankle)], stance_col, "", show, 2),
        Overlay("vline", [(float(lead_ankle[0]), foot_top), tuple(lead_ankle)], stance_col, "", show, 2),
        Overlay("segment", [tuple(shoulders[0]), tuple(shoulders[1])], stance_col, "", show, 2),
        Overlay("text", [(float(sh_mid[0]), float(sh_mid[1]) - 0.15 * s)], stance_col, stance_label, show),
        spot_mark(ball, ball_col, show, ball_label),
        Overlay("dashed", [tuple(hips), (float(hips[0]), float(hips[1]) - 1.1 * s)], REFERENCE_COLOR, "", show, 2),
        Overlay("segment", [tuple(hips), tuple(sh_mid)], tilt_col, "", show, 3),
        Overlay("text", [(float(hips[0]) + 0.1 * s, float(hips[1]) - 0.5 * s)], tilt_col, f"Spine {tilt:+.0f} deg", show),
    ]

    times = lambda x: f"{x:.1f}×"  # noqa: E731
    share = lambda x: f"{x * 100:.0f}%"  # noqa: E731
    return Verdict(
        status=status,
        label=label,
        summary=summary,
        tip=" ".join(tips),
        measurements={
            "stance_over_shoulders": round(stance, 3),
            "ball_position": round(position, 3),
            "spine_tilt_deg": round(tilt, 1),
            "units": "stance: ankle width over shoulder width; ball: 0 = back ankle, 1 = front ankle; "
                     "tilt: degrees from vertical, + = away from the target",
        },
        rows=[
            Row("Stance width", f"{stance:.1f}× your shoulders", stance_label.removeprefix("Stance ").capitalize(),
                stance_status, good=_range(cfg["stance_min"], cfg["stance_max"], times) + " shoulder width",
                fix=f"under {times(cfg['stance_watch_min'])} or over {times(cfg['stance_watch_max'])}"),
            Row("Ball position", f"{share(position)} of the way to your front foot",
                ball_label.removeprefix("Ball ").capitalize(), ball_status,
                good=_range(cfg["ball_min"], cfg["ball_max"], share) + " of the way",
                fix=f"under {share(cfg['ball_watch_min'])} or over {share(cfg['ball_watch_max'])}"),
            Row("Spine tilt", f"{deg_text(abs(tilt))} {'away from' if tilt >= 0 else 'toward'} the target",
                tilt_label, tilt_status,
                good=f"{deg_text(cfg['tilt_min'])} to {deg_text(cfg['tilt_max'])} away" if cfg["tilt_min"] >= 0 else
                     f"up to {deg_text(-cfg['tilt_min'])} toward, to {deg_text(cfg['tilt_max'])} away",
                fix=f"more than {deg_text(-cfg['tilt_watch_min'])} toward the target, or "
                    f"{deg_text(cfg['tilt_watch_max'])} away"),
        ],
        overlays=overlays,
    )
