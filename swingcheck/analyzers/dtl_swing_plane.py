"""Down-the-line: hand position against the shaft and shoulder planes.

Two lines from the ball:
  shaft plane    - along the shaft at address (clubhead -> grip direction, anchored at the ball)
  shoulder plane - ball through the trail shoulder at address

At takeaway, top and early downswing the hands are classified as on plane
(between the lines), steep/over (past the shoulder line) or shallow/under
(past the shaft line). A steep early downswing is the over-the-top move that
pairs with an out-to-in path and steep, fat or thin strikes.

The pose "hands" point is the wrists, which sit a little above and inside the
grip. At address the hands are on the shaft plane by definition, so by
default the hand path is shifted sideways by the wrists' address offset from
the shaft line.
"""

from __future__ import annotations

import numpy as np

from swingcheck.analyzers import (
    BALL_COLOR,
    REFERENCE_COLOR,
    STATUS_COLORS,
    MissingData,
    Overlay,
    SwingContext,
    Verdict,
    register,
)
from swingcheck.geometry import angle_deg, classify_in_wedge, inward_normal

CHECKPOINTS = ("takeaway", "top", "early_downswing")
ZONE_LABELS = {"inside": "on plane", "beyond_a": "steep", "beyond_b": "shallow"}
SHAFT_COLOR = (0, 200, 255)
SHOULDER_COLOR = (255, 120, 0)


def plane_lines(ctx: SwingContext) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """(ball, shaft direction, shoulder direction, trail shoulder at address)."""
    pts = ctx.marks.points
    ball = np.asarray(pts["ball"], dtype=float)
    shaft_dir = np.asarray(pts["grip"], dtype=float) - np.asarray(pts["clubhead"], dtype=float)
    if np.linalg.norm(shaft_dir) < 1:
        raise MissingData("clubhead and grip marks are on top of each other; re-mark with --remark")
    shoulder = ctx.at(ctx.track(ctx.side("shoulder", "trail")), "address")
    shoulder_dir = shoulder - ball
    return ball, shaft_dir, shoulder_dir, shoulder


@register("swing_plane", view="dtl", title="Swing plane")
def swing_plane(ctx: SwingContext) -> Verdict:
    ball, shaft_dir, shoulder_dir, shoulder = plane_lines(ctx)
    hands = ctx.hands()
    # At address the hands are on the shaft plane by definition; the wrist
    # landmark isn't quite (it sits above/inside the grip). Remove that
    # sideways offset so the path is measured as if it started on the line.
    n_in = inward_normal(shaft_dir, shoulder_dir)
    address_margin = float(np.dot(ctx.at(hands, "address") - ball, n_in))
    offset = -address_margin * n_in if ctx.cfg["calibrate_hands_to_shaft_line"] else np.zeros(2)
    path = hands + offset

    tol_px = ctx.cfg["tolerance"] * ctx.scale
    results = {}
    measurements: dict[str, object] = {}
    for cp in CHECKPOINTS:
        r = classify_in_wedge(ctx.at(path, cp), ball, shoulder_dir, shaft_dir, tol_px)
        results[cp] = ZONE_LABELS[r.zone]
        measurements[f"{cp}_zone"] = ZONE_LABELS[r.zone]
        # Positive = inside the wedge; negative = how far past that line.
        measurements[f"{cp}_shoulder_line_margin"] = round(ctx.units(r.margin_a), 3)
        measurements[f"{cp}_shaft_line_margin"] = round(ctx.units(r.margin_b), 3)
    measurements["shaft_line_angle_deg"] = round(angle_deg(shaft_dir), 1)
    measurements["shoulder_line_angle_deg"] = round(angle_deg(shoulder_dir), 1)
    measurements["address_wrist_offset_from_shaft_line"] = round(ctx.units(address_margin), 3)
    measurements["units"] = "margins in body lengths; + = inside the plane wedge, - = past that line"

    early = results["early_downswing"]
    off = [cp for cp in CHECKPOINTS if results[cp] != "on plane"]
    if early != "on plane":
        status = "flag"
    elif off:
        status = "warn"
    else:
        status = "ok"
    label = " / ".join(results[cp] for cp in CHECKPOINTS)
    summary = _summary(results)

    n = len(hands)
    overlays = [
        # The calibrated path, so the checkpoint dots sit on the drawn trail.
        Overlay("path", [tuple(p) for p in path], label="hand path"),
        Overlay("ray", [tuple(ball), tuple(ball + shaft_dir)], SHAFT_COLOR, "shaft plane"),
        Overlay("ray", [tuple(ball), tuple(shoulder)], SHOULDER_COLOR, "shoulder plane"),
        Overlay("point", [tuple(ball)], BALL_COLOR, "", thickness=1),
    ]
    for cp in CHECKPOINTS:
        zone = results[cp]
        color = STATUS_COLORS["ok"] if zone == "on plane" else STATUS_COLORS["flag" if cp == "early_downswing" else "warn"]
        overlays.append(
            Overlay("point", [tuple(ctx.at(path, cp))], color, f"{cp.replace('_', ' ')}: {zone}", frames=(ctx.frame(cp), n - 1))
        )
    overlays.append(Overlay("point", [tuple(ctx.at(path, "address"))], REFERENCE_COLOR, "", frames=None, thickness=1))
    return Verdict(status=status, label=label, summary=summary, measurements=measurements, overlays=overlays)


def _summary(results: dict[str, str]) -> str:
    early = results["early_downswing"]
    parts = []
    if early == "steep":
        parts.append("Hands above the shoulder plane in the early downswing: over the top / steep.")
    elif early == "shallow":
        parts.append("Hands below the shaft plane in the early downswing: stuck / under plane.")
    else:
        parts.append("Early downswing on plane.")
    for cp in ("takeaway", "top"):
        if results[cp] != "on plane":
            parts.append(f"{cp.capitalize()} {results[cp]}.")
    return " ".join(parts)
