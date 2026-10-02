"""Face-on: hip movement toward the target from address to impact.

Not getting the pelvis forward by impact leaves the low point of the swing
behind the ball, a common cause of fat shots. Measured as the hip center's
horizontal movement toward the target, in body units.
"""

from __future__ import annotations

from swingcheck.analyzers import REFERENCE_COLOR, STATUS_COLORS, Overlay, SwingContext, Verdict, register


@register("weight_shift", view="fo", title="Weight shift at impact")
def weight_shift(ctx: SwingContext) -> Verdict:
    hips = ctx.midpoint("left_hip", "right_hip")
    address_xy = ctx.at(hips, "address")
    impact_xy = ctx.at(hips, "impact")
    top_xy = ctx.at(hips, "top")

    shift = ctx.units((impact_xy[0] - address_xy[0]) * ctx.target_sign)
    at_top = ctx.units((top_xy[0] - address_xy[0]) * ctx.target_sign)

    if shift >= ctx.cfg["min_shift"]:
        status, label = "ok", "shifted"
        summary = "Hips moved toward the target by impact."
    else:
        status, label = "flag", "not enough"
        direction = "away from" if shift < 0 else "only slightly toward"
        summary = (
            f"Hips moved {direction} the target by impact: low point likely behind the ball (fat-shot risk)."
        )

    color = STATUS_COLORS[status]
    impact = ctx.frame("impact")
    return Verdict(
        status=status,
        label=label,
        summary=summary,
        measurements={
            "hip_shift_at_impact": round(shift, 3),
            "hip_shift_at_top": round(at_top, 3),
            "required": ctx.cfg["min_shift"],
            "units": "body lengths toward target from address",
        },
        overlays=[
            Overlay("vline", [tuple(address_xy)], REFERENCE_COLOR, "hips @ address", thickness=1),
            Overlay("vline", [tuple(impact_xy)], color, "hips @ impact", frames=(impact, len(hips) - 1)),
            Overlay("segment", [tuple(address_xy), (float(impact_xy[0]), float(address_xy[1]))], color, "",
                    frames=(impact, len(hips) - 1)),
        ],
    )
