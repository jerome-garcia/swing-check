"""Down-the-line checkpoint 4: halfway back.

On the frame you mark where the lead arm is parallel to the ground, using the
clubhead and hands you click there:

  shaft points   the shaft line, from the clubhead through the hands and on
                 down to the ball's level, should land at or just inside the
                 ball (between the ball and your feet). Well inside = pointing
                 at your feet (shaft too steep / upright); past the ball =
                 shaft too flat (laid off).

A distance as a share of torso length, with green / yellow / red bands in
[analyzers.halfway_back]. (A "hands split the biceps" check was tried and
dropped: from behind the trail elbow is half hidden at this point, so the
tracked biceps line wasn't reliable enough.)
"""

from __future__ import annotations

import numpy as np

from swingcheck.analyzers import (BALL_COLOR, STATUS_COLORS, MissingData, Overlay, Row, SwingContext, Verdict, grade, pct,
                                  register)
from swingcheck.analyzers.dtl_swing_plane import swing_plane_line

SHAFT_COLOR = (80, 230, 80)
HOLD_MS = 400  # how long the overlays stay up in the annotated video


def shaft_landing(ctx: SwingContext, clubhead, hands, where: str) -> tuple[np.ndarray, float, float]:
    """Where the shaft line (clubhead through hands, carried on down) reaches the ball's level.

    Returns (landing point, inside_by, toward_golfer): inside_by is in torso lengths,
    + = between the ball and your feet; toward_golfer is the screen x direction to the golfer.
    """
    clubhead, hands = np.asarray(clubhead, float), np.asarray(hands, float)
    ball = np.asarray(ctx.marks.points["ball"], float)
    if hands[1] - clubhead[1] < 1:
        raise MissingData(f"the clubhead should be above the hands at {where}; check the {where} marks")
    # Screen x direction from the ball toward the golfer (hips at address).
    hip = ctx.midpoint("left_hip", "right_hip")[ctx.marks.address_frame]
    if not np.all(np.isfinite(hip)):
        hip = ctx.value(ctx.track(ctx.side("hip", "trail")), ctx.marks.address_frame, "trail hip")
    toward_golfer = -1.0 if hip[0] < ball[0] else 1.0
    slope = (hands[0] - clubhead[0]) / (hands[1] - clubhead[1])  # screen x per screen y
    landing = np.array([hands[0] + (ball[1] - hands[1]) * slope, ball[1]])
    return landing, ctx.units((landing[0] - ball[0]) * toward_golfer), toward_golfer


@register("halfway_back", view="dtl", title="Halfway back")
def halfway_back(ctx: SwingContext) -> Verdict:
    mark = ctx.marks.checkpoint("halfway_back")
    if mark is None:
        raise MissingData("halfway back isn't marked yet: Edit marks → Halfway back, then click the clubhead and hands")
    cfg = ctx.cfg
    f = mark.frame
    clubhead = np.asarray(mark.points["clubhead"], float)  # or any point high up the shaft
    hands = np.asarray(mark.points["grip"], float)
    ball = np.asarray(ctx.marks.points["ball"], float)
    landing, inside_by, toward_golfer = shaft_landing(ctx, clubhead, hands, "halfway back")

    status = grade(inside_by, cfg["inside_min"], cfg["inside_max"], cfg["inside_watch_min"], cfg["inside_watch_max"])
    if status == "ok" and inside_by < 0:
        label, meaning = "Points at the ball", "the shaft points at the ball line, on plane"
    elif status == "ok":
        label, meaning = "Points just inside the ball", "the shaft points just inside the ball, on plane"
    elif inside_by > cfg["inside_max"]:
        label, meaning = (("Points well inside the ball", "the shaft points toward your feet: a little steep")
                          if status == "warn" else
                          ("Points at your feet", "the shaft points at your feet: too steep / upright"))
    else:
        label, meaning = (("Points just outside the ball", "the shaft points just past the ball: a little flat")
                          if status == "warn" else
                          ("Points outside the ball", "the shaft points well past the ball: too flat / laid off"))
    tip = "" if status == "ok" else (
        "Turn your chest more and let the club set a little more around you."
        if inside_by > cfg["inside_max"] else
        "Hinge your wrists more upward so the butt of the club points at the ball line.")

    # Drawing on the marked frame: the shaft line carried down to the ball's level, the
    # ball, and a tick from where it lands to the ball.
    s = ctx.scale
    show = (f, min(len(ctx.pose) - 1, f + int(round(HOLD_MS * ctx.fps / 1000))))
    col = STATUS_COLORS[status]
    overlays = [
        Overlay("segment", [tuple(clubhead), tuple(landing)], SHAFT_COLOR, "", show, 3),
        Overlay("segment", [tuple(landing), tuple(ball)], col, "", show, 2),
        Overlay("point", [tuple(ball)], BALL_COLOR, "", show, 1),
        Overlay("point", [tuple(landing)], col, "", show, 2),
        Overlay("point", [tuple(hands)], SHAFT_COLOR, "", show, 1),
        Overlay("point", [tuple(clubhead)], SHAFT_COLOR, "", show, 2),
        Overlay("text", [(float(landing[0]) - toward_golfer * 0.1 * s, float(landing[1]) + 0.2 * s)], col, label, show),
    ]

    side = "inside" if inside_by >= 0 else "outside"
    return Verdict(
        status=status,
        label=label,
        summary=f"Halfway back, {meaning}.",
        tip=tip,
        frame=f,
        measurements={
            "shaft_inside_ball": round(inside_by, 3),
            "halfway_frame": f,
            "units": "share of torso length; + = the shaft line lands between the ball and your feet (inside), "
                     "- = past the ball",
        },
        rows=[
            Row("Shaft points", f"{ctx.distance_text(inside_by)} {side} the ball",
                f"{pct(abs(inside_by))} of torso length · {label.lower()} "
                f"(green {pct(-cfg['inside_min'])} outside to {pct(cfg['inside_max'])} inside, "
                f"red past {pct(cfg['inside_watch_max'])} inside or {pct(-cfg['inside_watch_min'])} outside)", status),
            Row("Halfway frame", str(f), "marked by you", "ok"),
        ],
        overlays=swing_plane_line(ctx, show) + overlays,
    )
