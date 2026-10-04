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
from swingcheck.geometry import angle_between_deg, tilt_from_vertical_deg

HOLD_MS = 400  # how long the takeaway overlays stay up in the annotated video
ORDER = {"ok": 0, "warn": 1, "flag": 2}


@dataclass
class BodyCheck:
    status: str
    label: str  # "" when ok or not measured
    meaning: str
    tip: str
    row: Row
    overlays: list[Overlay]


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
        Overlay("point", [tuple(clubhead)], color, "", show, 2),
        # Label on the ball side of the clubhead, away from the body.
        Overlay("text", [(float(clubhead[0]) - toward_golfer * 0.15 * s, float(clubhead[1]) + 0.25 * s)], color, label, show),
    ]

    tip = "" if status == "ok" else (
        "Keep the clubhead outside your hands early: move the club, hands and chest back together."
        if inside_by > 0 else
        "Start the takeaway by turning your chest, without pushing your hands out toward the ball.")

    # Body: posture and trail knee kept from address.
    forward = -toward_golfer  # screen x direction toward the ball
    body = [_posture(ctx, f, forward, show), _trail_knee(ctx, f, forward, show)]
    plane_status = status
    status = max([plane_status] + [b.status for b in body], key=ORDER.__getitem__)
    faults = [b for b in body if b.label]
    if faults:
        label = ", ".join([label] + [b.label[0].lower() + b.label[1:] for b in faults])
        meaning = f"{meaning} Your {' and '.join(b.meaning for b in faults)}."
    tip = " ".join(t for t in [tip] + [b.tip for b in body] if t)
    for b in body:
        overlays += b.overlays

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


def _limits(cfg: dict, lose_max: str, lose_watch: str, lose_word: str, gain_max: str, gain_watch: str,
            gain_word: str) -> str:
    return (f"green up to {cfg[lose_max]:g}° {lose_word} or {cfg[gain_max]:g}° {gain_word}, "
            f"red past {cfg[lose_watch]:g}° {lose_word} or {cfg[gain_watch]:g}° {gain_word}")


def _posture(ctx: SwingContext, f: int, forward: float, show: tuple[int, int]) -> BodyCheck:
    """Spine bend at the takeaway vs address; lost = standing up."""
    cfg = ctx.cfg
    a = ctx.marks.address_frame
    hip0, sh0 = ctx.midpoint("left_hip", "right_hip")[a], ctx.midpoint("left_shoulder", "right_shoulder")[a]
    hip1, sh1 = ctx.midpoint("left_hip", "right_hip")[f], ctx.midpoint("left_shoulder", "right_shoulder")[f]
    if not all(np.all(np.isfinite(p)) for p in (hip0, sh0, hip1, sh1)):
        return BodyCheck("ok", "", "", "", Row("Spine bend kept", "not measured",
                         "hips or shoulders not tracked on the address or takeaway frame", "error"), [])
    bend0 = tilt_from_vertical_deg(sh0 - hip0, forward, up=True)
    bend1 = tilt_from_vertical_deg(sh1 - hip1, forward, up=True)
    lost = bend0 - bend1  # + = more upright
    status = grade(lost, -cfg["posture_gain_max"], cfg["posture_loss_max"],
                   -cfg["posture_gain_watch"], cfg["posture_loss_watch"])
    soft = status == "warn"
    if status == "ok":
        label = meaning = tip = ""
        word = "posture kept"
    elif lost > 0:
        label = "Slightly standing up" if soft else "Standing up"
        meaning = "spine is a little more upright than at address" if soft else "spine stands up from its address bend"
        tip = "Keep your spine angle as you start back: turn around it instead of lifting up."
        word = label.lower()
    else:
        label = "Slightly bending over" if soft else "Bending over"
        meaning = "spine bends a little more than at address" if soft else "spine bends over more than at address"
        tip = "Keep your spine angle as you start back instead of dipping your chest toward the ball."
        word = label.lower()
    limits = _limits(cfg, "posture_loss_max", "posture_loss_watch", "lost",
                     "posture_gain_max", "posture_gain_watch", "gained")
    row = Row("Spine bend kept", f"{bend1:.0f}° (address {bend0:.0f}°)",
              f"{abs(lost):.0f}° {'more upright' if lost >= 0 else 'more bent'} · {word} ({limits})", status)
    col = STATUS_COLORS[status]
    s = ctx.scale
    overlays = [
        Overlay("dashed", [tuple(hip1), tuple(hip1 + (sh0 - hip0))], REFERENCE_COLOR, "address spine", show, 2),
        Overlay("segment", [tuple(hip1), tuple(sh1)], col, "", show, 3),
        Overlay("text", [tuple((hip1 + sh1) / 2 - forward * np.array([0.55 * s, 0.0]))], col,
                f"spine {bend1:.0f} deg (address {bend0:.0f})", show),
    ]
    return BodyCheck(status, label, meaning, tip, row, overlays)


def _trail_knee(ctx: SwingContext, f: int, forward: float, show: tuple[int, int]) -> BodyCheck:
    """Trail knee flex at the takeaway vs address; lost = the leg straightening."""
    cfg = ctx.cfg
    a = ctx.marks.address_frame
    hip, knee, ankle = (ctx.track(ctx.side(p, "trail")) for p in ("hip", "knee", "ankle"))
    if not all(np.all(np.isfinite(t[i])) for t in (hip, knee, ankle) for i in (a, f)):
        return BodyCheck("ok", "", "", "", Row("Trail knee flex kept", "not measured",
                         "trail leg not tracked on the address or takeaway frame", "error"), [])
    flex0 = 180.0 - angle_between_deg(hip[a] - knee[a], ankle[a] - knee[a])
    flex1 = 180.0 - angle_between_deg(hip[f] - knee[f], ankle[f] - knee[f])
    lost = flex0 - flex1  # + = straighter
    status = grade(lost, -cfg["knee_bend_max"], cfg["knee_straighten_max"],
                   -cfg["knee_bend_watch"], cfg["knee_straighten_watch"])
    soft = status == "warn"
    if status == "ok":
        label = meaning = tip = ""
        word = "flex kept"
    elif lost > 0:
        label = "Trail knee slightly straightening" if soft else "Trail knee straightening"
        meaning = "trail knee straightens a little" if soft else "trail knee straightens, locking the trail leg"
        tip = "Keep the flex in your trail knee as you start back; let the hips turn without locking the leg."
        word = "slightly straightening" if soft else "straightening"
    else:
        label = "Trail knee slightly sinking" if soft else "Trail knee sinking"
        meaning = "trail knee bends a little more" if soft else "trail knee bends more, sinking down"
        tip = "Keep your trail knee flex as at address instead of squatting as you start back."
        word = "slightly sinking" if soft else "sinking"
    limits = _limits(cfg, "knee_straighten_max", "knee_straighten_watch", "straighter",
                     "knee_bend_max", "knee_bend_watch", "more bent")
    row = Row("Trail knee flex kept", f"{flex1:.0f}° (address {flex0:.0f}°)",
              f"{abs(lost):.0f}° {'straighter' if lost >= 0 else 'more bent'} · {word} ({limits})", status)
    col = STATUS_COLORS[status]
    s = ctx.scale
    overlays = [
        Overlay("polyline", [tuple(hip[f]), tuple(knee[f]), tuple(ankle[f])], col, "", show, 3),
        Overlay("text", [(float(knee[f][0]) - forward * 0.55 * s, float(knee[f][1]))], col,
                f"knee {flex1:.0f} deg (address {flex0:.0f})", show),
    ]
    return BodyCheck(status, label, meaning, tip, row, overlays)
