"""Face-on: hands ahead of, level with, or behind the ball at impact.

Hands behind the ball at impact means the shaft is leaning back (scooping),
which adds loft: wedges and hybrids fly higher and shorter. Measured as the
hands' horizontal distance from the ball toward the target, in body units.
"""

from __future__ import annotations

from swingcheck.analyzers import BALL_COLOR, STATUS_COLORS, Overlay, SwingContext, Verdict, register


@register("hands_at_impact", view="fo", title="Hands at impact", phase="impact")
def hands_at_impact(ctx: SwingContext) -> Verdict:
    ball_x = ctx.marks.points["ball"][0]
    hands = ctx.hands()
    address_xy = ctx.at(hands, "address")
    impact_xy = ctx.at(hands, "impact")

    ahead_address = ctx.units((address_xy[0] - ball_x) * ctx.target_sign)
    ahead_impact = ctx.units((impact_xy[0] - ball_x) * ctx.target_sign)

    if ahead_impact >= ctx.cfg["ahead_threshold"]:
        status, label = "ok", "ahead"
        summary = "Hands ahead of the ball at impact: shaft leaning toward the target."
    elif ahead_impact <= ctx.cfg["behind_threshold"]:
        status, label = "flag", "behind"
        summary = "Hands behind the ball at impact: shaft leaning back (scoop). Adds loft and moves the low point back."
    else:
        status, label = "warn", "level"
        summary = "Hands roughly level with the ball at impact: little forward shaft lean."

    color = STATUS_COLORS[status]
    impact = ctx.frame("impact")
    ball_y = ctx.marks.points["ball"][1]
    return Verdict(
        status=status,
        label=label,
        summary=summary,
        measurements={
            "hands_ahead_at_impact": round(ahead_impact, 3),
            "hands_ahead_at_address": round(ahead_address, 3),
            "change_from_address": round(ahead_impact - ahead_address, 3),
            "units": "body lengths toward target (+ = ahead of ball)",
        },
        overlays=[
            # Ball line from the ball up to hand height: hands left/right of it is the verdict.
            Overlay("vline", [(ball_x, ball_y), (ball_x, float(address_xy[1]) - 0.15 * ctx.scale)], BALL_COLOR,
                    "ball", thickness=1),
            Overlay("point", [(ball_x, ball_y)], BALL_COLOR, "", thickness=1),
            Overlay("point", [tuple(impact_xy)], color, f"hands {label}", frames=(impact, len(hands) - 1)),
        ],
    )
