"""Down-the-line checkpoint 7: impact.

Automatic, on the detected impact frame (adjust it on the results page if it's
off); no extra marks needed:

  hips (tush line)  the back edge of your body outline at hip height, at impact
                    vs at address. It should stay on the line it set at address;
                    moving toward the ball is early extension (hips thrusting
                    in, which stands you up and pushes the hands out).
  posture           spine bend (hip center -> shoulder center, from vertical)
                    at impact vs address. Losing a lot of it = standing up
                    through the ball; gaining a lot = dipping.

Bands are in [analyzers.impact].
"""

from __future__ import annotations

import numpy as np

from swingcheck import pose as pose_mod
from swingcheck.analyzers import (REFERENCE_COLOR, STATUS_COLORS, MissingData, Overlay, Row, SwingContext, Verdict, grade,
                                  pct, register)
from swingcheck.geometry import tilt_from_vertical_deg

ORDER = {"ok": 0, "warn": 1, "flag": 2}
HOLD_MS = 300


def back_edge_x(mask: np.ndarray, hip: np.ndarray, toward_back: float, half_height: float, reach: float) -> float:
    """Screen x of the rearmost body pixel at hip height: the median, over rows within
    half_height of the hip, of the farthest mask pixel toward the golfer's back (searched
    from a little in front of the hip joint to `reach` px behind it)."""
    h, w = mask.shape[:2]
    xs = []
    for y in range(int(max(0, hip[1] - half_height)), int(min(h - 1, hip[1] + half_height)) + 1):
        # Search from a little in front of the hip joint (the rear edge can pass it when
        # the hips thrust) back to `reach` behind it.
        ahead = 0.4 * reach
        lo, hi = (hip[0] - reach, hip[0] + ahead) if toward_back < 0 else (hip[0] - ahead, hip[0] + reach)
        lo, hi = int(max(0, lo)), int(min(w - 1, hi))
        row = np.flatnonzero(mask[y, lo:hi + 1] >= 0.5)
        if row.size:
            xs.append(lo + (row.min() if toward_back < 0 else row.max()))
    if not xs:
        raise MissingData("couldn't find the outline of your hips")
    return float(np.median(xs))


@register("impact", view="dtl", title="Impact", phase="impact")
def impact(ctx: SwingContext) -> Verdict:
    cfg = ctx.cfg
    a, f = ctx.marks.address_frame, ctx.frame("impact")
    ball = np.asarray(ctx.marks.points["ball"], float)

    def centers(frame):
        hip = ctx.midpoint("left_hip", "right_hip")[frame]
        sh = ctx.midpoint("left_shoulder", "right_shoulder")[frame]
        if not (np.all(np.isfinite(hip)) and np.all(np.isfinite(sh))):
            raise MissingData(f"hips or shoulders not tracked on frame {frame}")
        return hip, sh

    hip0, sh0 = centers(a)
    hip1, sh1 = centers(f)
    toward_back = -1.0 if hip0[0] < ball[0] else 1.0  # screen x direction toward the golfer's back
    forward = -toward_back  # toward the ball

    # 1. Tush line: rear edge of the hips at address and impact.
    s = ctx.scale
    edges = {}
    for name, frame, hip in (("address", a, hip0), ("impact", f, hip1)):
        mask = pose_mod.segment_frame(ctx.image(frame), ctx.config)
        edges[name] = back_edge_x(mask, hip, toward_back, 0.08 * s, 0.8 * s)
    toward_ball = ctx.units((edges["impact"] - edges["address"]) * forward)  # + = hips moved toward the ball
    hips_status = grade(toward_ball, -np.inf, cfg["hips_forward_max"], -np.inf, cfg["hips_forward_watch"])
    if hips_status == "ok":
        hips_label, hips_meaning = "Hips on the tush line", "your hips stay back on the line they set at address"
    elif hips_status == "warn":
        hips_label, hips_meaning = "Hips slightly off the tush line", "your hips move a little toward the ball (slight early extension)"
    else:
        hips_label, hips_meaning = "Early extension", "your hips thrust toward the ball, off the tush line (early extension)"

    # 2. Posture: spine bend kept from address.
    bend0 = tilt_from_vertical_deg(sh0 - hip0, forward, up=True)
    bend1 = tilt_from_vertical_deg(sh1 - hip1, forward, up=True)
    lost = bend0 - bend1  # + = more upright at impact
    posture_status = grade(lost, -cfg["posture_gain_max"], cfg["posture_loss_max"],
                           -cfg["posture_gain_watch"], cfg["posture_loss_watch"])
    if posture_status == "ok":
        posture_label, posture_meaning = "Posture kept", "you keep your spine bend through the ball"
    elif lost > 0:
        posture_label = "Slightly standing up" if posture_status == "warn" else "Standing up"
        posture_meaning = ("you stand up a little through the ball" if posture_status == "warn" else
                           "you stand up through the ball, losing your spine bend")
    else:
        posture_label = "Slightly dipping" if posture_status == "warn" else "Dipping"
        posture_meaning = ("you bend a little more through the ball" if posture_status == "warn" else
                           "you bend over more through the ball (dipping)")

    status = max(hips_status, posture_status, key=ORDER.__getitem__)
    label = f"{hips_label}, {posture_label[0].lower() + posture_label[1:]}"
    summary = f"At impact, {hips_meaning}, and {posture_meaning}."

    # Drawing on the impact frame: the address tush line (white) and the impact hip edge,
    # plus the spine now and at address.
    show = (f, min(len(ctx.pose) - 1, f + int(round(HOLD_MS * ctx.fps / 1000))))
    hips_col, posture_col = STATUS_COLORS[hips_status], STATUS_COLORS[posture_status]
    y_top, y_bot = float(hip0[1] - 0.6 * s), float(hip0[1] + 0.5 * s)
    overlays = [
        Overlay("vline", [(edges["address"], y_top), (edges["address"], y_bot)], REFERENCE_COLOR, "", show, 2),
        Overlay("segment", [(edges["impact"], float(hip1[1]) - 0.15 * s), (edges["impact"], float(hip1[1]) + 0.15 * s)],
                hips_col, "", show, 4),
        Overlay("segment", [(edges["address"], float(hip1[1])), (edges["impact"], float(hip1[1]))], hips_col, "", show, 2),
        Overlay("text", [(edges["address"] + forward * 0.08 * s, y_top + 0.1 * s)], hips_col, hips_label, show),
        Overlay("dashed", [tuple(hip1), tuple(hip1 + (sh0 - hip0))], REFERENCE_COLOR, "address spine", show, 2),
        Overlay("segment", [tuple(hip1), tuple(sh1)], posture_col, "", show, 3),
        Overlay("text", [tuple((hip1 + sh1) / 2 + forward * np.array([0.15 * s, 0.0]))], posture_col,
                f"spine {bend1:.0f} deg (address {bend0:.0f})", show),
    ]

    moved = "toward the ball" if toward_ball >= 0 else "back"
    return Verdict(
        status=status,
        label=label,
        summary=summary,
        measurements={
            "hips_toward_ball": round(toward_ball, 3),
            "spine_bend_address_deg": round(bend0, 1),
            "spine_bend_impact_deg": round(bend1, 1),
            "posture_lost_deg": round(lost, 1),
            "impact_frame": f,
            "units": "hips: share of torso length, + = rear of the hips moved toward the ball since address; "
                     "posture: degrees of spine bend lost since address (+ = more upright)",
        },
        rows=[
            Row("Hips vs tush line", f"{ctx.distance_text(toward_ball)} {moved}",
                f"{pct(abs(toward_ball))} of torso length · {hips_label.lower()} "
                f"(green up to {pct(cfg['hips_forward_max'])} toward the ball, red past {pct(cfg['hips_forward_watch'])})",
                hips_status),
            Row("Spine bend kept", f"{bend1:.0f}° (address {bend0:.0f}°)",
                f"{abs(lost):.0f}° {'more upright' if lost >= 0 else 'more bent'} · {posture_label.lower()} "
                f"(green up to {cfg['posture_loss_max']:g}° lost, red past {cfg['posture_loss_watch']:g}°)",
                posture_status),
            Row("Impact frame", str(f), "detected (adjust under Phases)", "ok"),
        ],
        overlays=overlays,
    )
