"""Face-on: horizontal head movement from address to impact.

A head that drifts away from the target by impact usually means the weight
hung back, which pairs with fat shots and scooping. Measured on a head center
(visibility-weighted nose and ears, steadier than the nose alone as the head
turns), in body units.
"""

from __future__ import annotations

import numpy as np

from swingcheck.analyzers import REFERENCE_COLOR, STATUS_COLORS, Overlay, SwingContext, Verdict, register

HEAD_POINTS = ("nose", "left_ear", "right_ear")


def head_center(ctx: SwingContext) -> np.ndarray:
    tracks = np.stack([ctx.track(name) for name in HEAD_POINTS])  # (3, frames, 2)
    return np.nanmean(tracks, axis=0) if np.isfinite(tracks).any() else tracks[0]


@register("head_drift", view="fo", title="Head drift")
def head_drift(ctx: SwingContext) -> Verdict:
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # all-NaN frames -> NaN, handled by ctx.at
        head = head_center(ctx)
    address_xy = ctx.at(head, "address")
    impact_xy = ctx.at(head, "impact")

    toward = ctx.units((impact_xy[0] - address_xy[0]) * ctx.target_sign)
    away = -toward
    limit = ctx.cfg["max_drift_away"]

    if away > limit:
        status, label = "flag", "drifted back"
        summary = "Head moved away from the target by impact: weight likely hanging back."
    else:
        status, label = "ok", "steady" if abs(toward) <= limit else "moved forward"
        summary = (
            "Head stayed steady from address to impact."
            if label == "steady"
            else "Head moved toward the target by impact (not flagged in v1)."
        )

    color = STATUS_COLORS[status]
    impact = ctx.frame("impact")
    return Verdict(
        status=status,
        label=label,
        summary=summary,
        measurements={
            "head_move_toward_target": round(toward, 3),
            "max_drift_away": limit,
            "units": "body lengths toward target from address (- = away)",
        },
        overlays=[
            Overlay("vline", ctx.vspan(address_xy, 0.2), REFERENCE_COLOR, "head @ address", thickness=1),
            Overlay("point", [tuple(impact_xy)], color, f"head {label}", frames=(impact, len(head) - 1)),
        ],
    )
