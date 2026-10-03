"""Down-the-line checkpoint 3: takeaway.

On the takeaway frame you mark (shaft parallel to the target line, so from
behind it points at the camera), the clubhead should sit in front of the
hands, "covering" them. Measured as the clubhead's sideways offset from the
hands, in body lengths:

  covering   within the tolerance either way (camera angle means it rarely
             lines up exactly)
  inside     clubhead toward the golfer: taken away behind the hands
  outside    clubhead toward the ball: taken away in front of the hands

The key frame also shows the address shaft line, with a tick from the
clubhead down to it, for comparison with the address position.
"""

from __future__ import annotations

import numpy as np

from swingcheck.analyzers import REFERENCE_COLOR, STATUS_COLORS, MissingData, Overlay, Row, SwingContext, Verdict, register

PLANE_COLOR = (0, 140, 255)
HOLD_MS = 400  # how long the takeaway overlays stay up in the annotated video


@register("takeaway", view="dtl", title="Takeaway", phase="takeaway")
def takeaway(ctx: SwingContext) -> Verdict:
    mark = ctx.marks.checkpoint("takeaway")
    if mark is None:
        raise MissingData("the takeaway isn't marked yet: Edit marks → Takeaway, then click the clubhead and hands")
    tol = ctx.cfg["covering_tolerance"]
    clubhead = np.asarray(mark.points["clubhead"], float)
    hands = np.asarray(mark.points["grip"], float)
    pts = ctx.marks.points
    ball = np.asarray(pts["ball"], float)
    f = mark.frame

    # "Toward the golfer" on screen: from the ball toward the hips at address.
    hip = ctx.midpoint("left_hip", "right_hip")[ctx.marks.address_frame]
    if not np.all(np.isfinite(hip)):
        hip = ctx.value(ctx.track(ctx.side("hip", "trail")), ctx.marks.address_frame, "trail hip")
    toward_golfer = -1.0 if hip[0] < ball[0] else 1.0  # screen x direction pointing at the golfer
    # inside_by > 0: clubhead is on the golfer's side of the hands.
    inside_by = ctx.units((clubhead[0] - hands[0]) * toward_golfer)

    if inside_by > tol:
        status, label = "flag", "Clubhead inside the hands"
        meaning = "Taken away too far inside: the club is behind your hands."
    elif inside_by < -tol:
        status, label = "flag", "Clubhead outside the hands"
        meaning = "Taken away outside: the club is in front of your hands."
    else:
        status, label = "ok", "Club covers the hands"
        meaning = "The clubhead sits in front of your hands, on the same line as at address."
    side = "inside" if inside_by > 0 else "outside"
    offset_text = f"{abs(inside_by):.2f} {side}" if abs(inside_by) >= 0.005 else "0.00"

    # Drawing on the takeaway frame: the address shaft line (as in checkpoint 2), a
    # vertical reference through the hands with the tolerance band, both points, and a
    # tick from the clubhead down to the address shaft line.
    s = ctx.scale
    show = (f, min(len(ctx.pose) - 1, f + int(round(HOLD_MS * ctx.fps / 1000))))
    color = STATUS_COLORS[status]
    ch0, gr0 = np.asarray(pts["clubhead"], float), np.asarray(pts["grip"], float)
    overlays = [
        Overlay("line", [tuple(ch0), tuple(gr0)], PLANE_COLOR, "", show, 2),
        Overlay("vline", [(float(hands[0]), float(hands[1]) - 0.35 * s), (float(hands[0]), float(hands[1]) + 0.35 * s)],
                REFERENCE_COLOR, "", show, 1),
    ]
    for edge in (-tol, tol):
        x = float(hands[0] + edge * s * toward_golfer)
        overlays.append(Overlay("segment", [(x, float(hands[1]) - 0.12 * s), (x, float(hands[1]) + 0.12 * s)],
                                (150, 150, 150), "", show, 1))
    drop = _vertical_drop_to_line(clubhead, ch0, gr0)
    if drop is not None:
        overlays.append(Overlay("segment", [tuple(clubhead), tuple(drop)], PLANE_COLOR, "", show, 2))
    overlays += [
        Overlay("point", [tuple(hands)], REFERENCE_COLOR, "", show, 1),
        Overlay("point", [tuple(clubhead)], color, "", show, 2),
        # Label on the ball side of the clubhead, away from the body.
        Overlay("text", [(float(clubhead[0]) - toward_golfer * 0.15 * s, float(clubhead[1]) + 0.25 * s)], color, label, show),
    ]

    return Verdict(
        status=status,
        label=label,
        summary=meaning,
        measurements={
            "clubhead_inside_hands": round(inside_by, 3),
            "covering_tolerance": tol,
            "takeaway_frame": f,
            "units": "body lengths; + = clubhead on the golfer's side of the hands (inside), - = ball side (outside)",
        },
        rows=[
            Row("Clubhead vs hands", offset_text, label.removeprefix("Clubhead ").removeprefix("Club "), status),
            Row("Takeaway frame", str(f), "marked by you", "ok"),
        ],
        overlays=overlays,
    )


def _vertical_drop_to_line(p: np.ndarray, a: np.ndarray, b: np.ndarray) -> np.ndarray | None:
    """Point straight below/above p on the infinite line through a and b (None if the line is vertical)."""
    d = b - a
    if abs(d[0]) < 1e-6:
        return None
    y = a[1] + (p[0] - a[0]) * d[1] / d[0]
    return np.array([p[0], y])
