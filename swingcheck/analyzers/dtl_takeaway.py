"""Down-the-line checkpoint 3: takeaway.

On the takeaway frame you mark (shaft parallel to the target line, so from
behind it points at the camera), the clubhead should still be on the shaft
line you set at address: the club is on plane. Measured as the clubhead's
distance from that line (square to it), as a share of torso length:

  on the line        within line_tolerance either way (OK)
  slightly in / out  up to flag_distance: a style many good players have (Watch)
  well inside        clubhead far behind the line, on your side: pulled inside /
                     rolled open (Flag)
  well outside       clubhead far in front of the line, toward the ball: picked
                     up outside (Flag)

Camera aim matters here: the clubhead is about a metre closer to the camera
than at address, so a camera pointed a few degrees off the target line shifts
it sideways. That's one reason for the Watch band.

Where the hands are doesn't matter for this, so only the clubhead is clicked.

Two body checks from tracking, takeaway frame vs address (no extra marks):

  posture     spine bend (hip center -> shoulder center, from vertical) kept;
              losing it = standing up early, gaining it = bending over.
  trail knee  trail knee flex (180 - hip-knee-ankle angle) kept; losing it =
              the trail leg straightening (locking out), gaining it = sinking.

The card shows the worst of the three. A body point not tracked on either
frame makes that row "not measured" without failing the check.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from swingcheck.analyzers import (REFERENCE_COLOR, STATUS_COLORS, MissingData, Overlay, Row, SwingContext, Verdict, grade,
                                  pct, register)
from swingcheck.analyzers.dtl_swing_plane import swing_plane_line
from swingcheck.analyzers.dtl_body import posture_kept, trail_knee_kept, with_body

HOLD_MS = 400  # how long the takeaway overlays stay up in the annotated video


@dataclass
class AddressLine:
    """The address shaft line (clicked clubhead -> grip) and its golfer-side normal."""

    clubhead: np.ndarray
    grip: np.ndarray
    normal: np.ndarray  # unit, square to the line, pointing to the golfer's side
    toward_golfer: float  # screen x direction pointing at the golfer (+1 or -1)

    def inside_by(self, ctx: SwingContext, point) -> float:
        """Distance of a point from the line, square to it, in torso lengths; + = golfer's side (inside)."""
        return ctx.units(float(np.dot(np.asarray(point, float) - self.clubhead, self.normal)))


def address_line(ctx: SwingContext) -> AddressLine:
    pts = ctx.marks.points
    ball = np.asarray(pts["ball"], float)
    ch0, gr0 = np.asarray(pts["clubhead"], float), np.asarray(pts["grip"], float)
    if np.linalg.norm(gr0 - ch0) < 1:
        raise MissingData("the address clubhead and grip marks are on top of each other")
    # "Toward the golfer" on screen: from the ball toward the hips at address.
    hip = ctx.midpoint("left_hip", "right_hip")[ctx.marks.address_frame]
    if not np.all(np.isfinite(hip)):
        hip = ctx.value(ctx.track(ctx.side("hip", "trail")), ctx.marks.address_frame, "trail hip")
    toward_golfer = -1.0 if hip[0] < ball[0] else 1.0
    d = (gr0 - ch0) / np.linalg.norm(gr0 - ch0)
    normal = np.array([-d[1], d[0]])
    if normal[0] * toward_golfer < 0:
        normal = -normal
    return AddressLine(ch0, gr0, normal, toward_golfer)


@register("takeaway", view="dtl", title="Takeaway", phase="takeaway")
def takeaway(ctx: SwingContext) -> Verdict:
    mark = ctx.marks.checkpoint("takeaway")
    if mark is None:
        raise MissingData("the takeaway isn't marked yet: Edit marks → Takeaway, then click the clubhead")
    tol = ctx.cfg["line_tolerance"]
    flag_at = ctx.cfg["flag_distance"]
    clubhead = np.asarray(mark.points["clubhead"], float)
    f = mark.frame
    line = address_line(ctx)
    ch0, gr0, normal, toward_golfer = line.clubhead, line.grip, line.normal, line.toward_golfer
    inside_by = line.inside_by(ctx, clubhead)

    if inside_by > flag_at:
        status, label = "flag", "Clubhead well inside the swing plane"
        meaning = "Taken away too far inside: the clubhead is well behind your swing plane line (the address shaft line)."
    elif inside_by < -flag_at:
        status, label = "flag", "Clubhead well outside the swing plane"
        meaning = "Taken away outside: the clubhead is well in front of your swing plane line (the address shaft line)."
    elif inside_by > tol:
        status, label = "warn", "Clubhead slightly inside the swing plane"
        meaning = "A little inside your swing plane line (the address shaft line). Many good players go back like this; watch it doesn't grow."
    elif inside_by < -tol:
        status, label = "warn", "Clubhead slightly outside the swing plane"
        meaning = "A little outside your swing plane line (the address shaft line). Many good players go back like this; watch it doesn't grow."
    else:
        status, label = "ok", "Club on plane"
        meaning = "The clubhead is still on your swing plane line (the address shaft line)."
    plane_label = label
    side = "inside" if inside_by > 0 else "outside"
    offset_text = f"{ctx.distance_text(inside_by)} {side}" if abs(inside_by) >= 0.005 else "on the plane line"

    # Drawing on the takeaway frame: the address shaft line (as in checkpoint 2) with
    # the tolerance band either side, a square-on tick from the clubhead to the line,
    # and the clicked clubhead.
    s = ctx.scale
    show = (f, min(len(ctx.pose) - 1, f + int(round(HOLD_MS * ctx.fps / 1000))))
    color = STATUS_COLORS[status]
    foot = clubhead - np.dot(clubhead - ch0, normal) * normal
    overlays = swing_plane_line(ctx, show) + [
        Overlay("segment", [tuple(clubhead), tuple(foot)], color, "", show, 2),
        # Label on the ball side of the clubhead, away from the body.
        Overlay("text", [(float(clubhead[0]) - toward_golfer * 0.15 * s, float(clubhead[1]) + 0.25 * s)], color, label, show),
    ]

    tip = "" if status == "ok" else (
        "Keep the clubhead outside your hands early: move the club, hands and chest back together."
        if inside_by > 0 else
        "Start the takeaway by turning your chest, without pushing your hands out toward the ball.")

    # Body: posture and trail knee kept from address.
    forward = -toward_golfer  # screen x direction toward the ball
    body = [posture_kept(ctx, f, forward, show), trail_knee_kept(ctx, f, forward, show)]
    plane_status = status
    status, label, meaning, tip = with_body(status, label, meaning, tip, body)
    for b in body:
        overlays += b.overlays
    # The clubhead last, on top of the body lines, with a white ring so it stands out
    # even where it crosses a line of the same color (e.g. a green spine).
    overlays += [Overlay("point", [tuple(clubhead)], color, "", show, 2),
                 Overlay("point", [tuple(clubhead)], REFERENCE_COLOR, "", show, 1)]

    return Verdict(
        status=status,
        label=label,
        summary=meaning,
        tip=tip,
        measurements={
            "clubhead_inside_line": round(inside_by, 3),
            "line_tolerance": tol,
            "flag_distance": flag_at,
            "takeaway_frame": f,
            "units": "share of torso length, square to the address shaft line; + = golfer's side (inside), "
                     "- = ball side (outside)",
        },
        rows=[
            Row("Clubhead vs swing plane", offset_text,
                f"{pct(abs(inside_by))} of torso length · {_note(plane_label, tol, flag_at)}", plane_status),
        ] + [b.row for b in body],
        overlays=overlays,
    )


def _note(label: str, tol: float, flag_at: float) -> str:
    """Card note with the bands, e.g. 'slightly inside the line (green within ±20%, red past 50%)'."""
    short = label.removeprefix("Clubhead ").removeprefix("Club ")
    return f"{short} (green within ±{pct(tol)}, red past {pct(flag_at)})"
