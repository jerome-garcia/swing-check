"""Down-the-line checkpoint 3: takeaway.

On the takeaway frame you mark (shaft parallel to the target line, so from
behind it points at the camera), the clubhead should still be on the shaft
line you set at address: the club is on plane. Measured as the clubhead's
distance from that line (square to it), in body lengths:

  on the line        within line_tolerance either way (OK)
  slightly in / out  up to flag_distance: a style many good players have (Watch)
  well inside        clubhead far behind the line, on your side: pulled inside /
                     rolled open (Flag)
  well outside       clubhead far in front of the line, toward the ball: picked
                     up outside (Flag)

Camera aim matters here: the clubhead is about a metre closer to the camera
than at address, so a camera pointed a few degrees off the target line shifts
it sideways. That's one reason for the Watch band.

Where the hands are doesn't matter for this; the key frame shows them for
reference.
"""

from __future__ import annotations

import numpy as np

from swingcheck.analyzers import REFERENCE_COLOR, STATUS_COLORS, MissingData, Overlay, Row, SwingContext, Verdict, register

PLANE_COLOR = (0, 140, 255)
BAND_COLOR = (150, 150, 150)
HOLD_MS = 400  # how long the takeaway overlays stay up in the annotated video


@register("takeaway", view="dtl", title="Takeaway", phase="takeaway")
def takeaway(ctx: SwingContext) -> Verdict:
    mark = ctx.marks.checkpoint("takeaway")
    if mark is None:
        raise MissingData("the takeaway isn't marked yet: Edit marks → Takeaway, then click the clubhead and hands")
    tol = ctx.cfg["line_tolerance"]
    flag_at = ctx.cfg["flag_distance"]
    clubhead = np.asarray(mark.points["clubhead"], float)
    hands = np.asarray(mark.points["grip"], float)
    pts = ctx.marks.points
    ball = np.asarray(pts["ball"], float)
    ch0, gr0 = np.asarray(pts["clubhead"], float), np.asarray(pts["grip"], float)
    f = mark.frame
    if np.linalg.norm(gr0 - ch0) < 1:
        raise MissingData("the address clubhead and grip marks are on top of each other")

    # "Toward the golfer" on screen: from the ball toward the hips at address.
    hip = ctx.midpoint("left_hip", "right_hip")[ctx.marks.address_frame]
    if not np.all(np.isfinite(hip)):
        hip = ctx.value(ctx.track(ctx.side("hip", "trail")), ctx.marks.address_frame, "trail hip")
    toward_golfer = -1.0 if hip[0] < ball[0] else 1.0  # screen x direction pointing at the golfer

    # Unit normal to the address shaft line, pointing to the golfer's side.
    d = (gr0 - ch0) / np.linalg.norm(gr0 - ch0)
    normal = np.array([-d[1], d[0]])
    if normal[0] * toward_golfer < 0:
        normal = -normal
    # inside_by > 0: clubhead on the golfer's side of the line (inside).
    inside_by = ctx.units(float(np.dot(clubhead - ch0, normal)))

    if inside_by > flag_at:
        status, label = "flag", "Clubhead well inside the line"
        meaning = "Taken away too far inside: the clubhead is well behind your address shaft line."
    elif inside_by < -flag_at:
        status, label = "flag", "Clubhead well outside the line"
        meaning = "Taken away outside: the clubhead is well in front of your address shaft line."
    elif inside_by > tol:
        status, label = "warn", "Clubhead slightly inside the line"
        meaning = "A little inside your address shaft line. Many good players go back like this; watch it doesn't grow."
    elif inside_by < -tol:
        status, label = "warn", "Clubhead slightly outside the line"
        meaning = "A little outside your address shaft line. Many good players go back like this; watch it doesn't grow."
    else:
        status, label = "ok", "Club on plane"
        meaning = "The clubhead is still on your address shaft line."
    side = "inside" if inside_by > 0 else "outside"
    offset_text = f"{abs(inside_by):.2f} {side}" if abs(inside_by) >= 0.005 else "0.00"

    # Drawing on the takeaway frame: the address shaft line (as in checkpoint 2) with
    # the tolerance band either side, a square-on tick from the clubhead to the line,
    # and the clicked points.
    s = ctx.scale
    show = (f, min(len(ctx.pose) - 1, f + int(round(HOLD_MS * ctx.fps / 1000))))
    color = STATUS_COLORS[status]
    foot = clubhead - np.dot(clubhead - ch0, normal) * normal
    overlays = [Overlay("line", [tuple(ch0), tuple(gr0)], PLANE_COLOR, "", show, 2)]
    for edge in (-tol, tol):
        off = normal * edge * s
        overlays.append(Overlay("line", [tuple(ch0 + off), tuple(gr0 + off)], BAND_COLOR, "", show, 1))
    overlays += [
        Overlay("segment", [tuple(clubhead), tuple(foot)], color, "", show, 2),
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
            "clubhead_inside_line": round(inside_by, 3),
            "line_tolerance": tol,
            "flag_distance": flag_at,
            "takeaway_frame": f,
            "units": "body lengths, square to the address shaft line; + = golfer's side (inside), - = ball side (outside)",
        },
        rows=[
            Row("Clubhead vs shaft line", offset_text, _note(label, status, tol, flag_at), status),
            Row("Takeaway frame", str(f), "marked by you", "ok"),
        ],
        overlays=overlays,
    )


def _note(label: str, status: str, tol: float, flag_at: float) -> str:
    """Card note with the band that applies, e.g. 'slightly inside the line (flag past 0.45)'."""
    short = label.removeprefix("Clubhead ").removeprefix("Club ")
    if status == "ok":
        return f"{short} (within ±{tol:g})"
    if status == "warn":
        return f"{short} (flag past {flag_at:g})"
    return f"{short} (on plane within ±{tol:g})"
