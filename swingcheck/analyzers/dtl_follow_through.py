"""Down-the-line checkpoint 8: follow-through.

On the frame you mark where the trail arm is parallel to the ground after
impact (the mirror of halfway back), using the clubhead and hands you click:

  shaft points     the shaft line, from the clubhead through the hands and on
                   down to the ball's level, as at halfway back. Exiting on
                   plane it lands at or just inside the ball.
  same line        that landing vs the one at halfway back: the club should exit
                   on the same line it went back on. More inside = a steeper
                   exit than the backswing; more outside = a flatter one.
                   Needs halfway back marked.

Distances are shares of torso length; bands are in [analyzers.follow_through].
"""

from __future__ import annotations

import numpy as np

from swingcheck.analyzers import (BALL_COLOR, STATUS_COLORS, MissingData, Overlay, Row, SwingContext, Verdict, grade, pct,
                                  register)
from swingcheck.analyzers.dtl_halfway_back import shaft_landing

SHAFT_COLOR = (80, 230, 80)
BACK_COLOR = (200, 200, 200)
HOLD_MS = 400
ORDER = {"ok": 0, "warn": 1, "flag": 2}


@register("follow_through", view="dtl", title="Follow-through")
def follow_through(ctx: SwingContext) -> Verdict:
    mark = ctx.marks.checkpoint("follow_through")
    if mark is None:
        raise MissingData("the follow-through isn't marked yet: Edit marks → Follow-through, then click the clubhead and hands")
    cfg = ctx.cfg
    f = mark.frame
    clubhead = np.asarray(mark.points["clubhead"], float)
    hands = np.asarray(mark.points["grip"], float)
    ball = np.asarray(ctx.marks.points["ball"], float)
    landing, inside_by, toward_golfer = shaft_landing(ctx, clubhead, hands, "the follow-through")

    # 1. Where it points.
    shaft_status = grade(inside_by, cfg["inside_min"], cfg["inside_max"], cfg["inside_watch_min"], cfg["inside_watch_max"])
    soft = shaft_status == "warn"
    if shaft_status == "ok":
        shaft_label, shaft_meaning = "Exits on plane", "the shaft points at the ball line, on plane"
    elif inside_by > cfg["inside_max"]:
        shaft_label = "Exits slightly steep" if soft else "Exits steep"
        shaft_meaning = "the shaft points toward your feet: " + ("a little steep" if soft else "a steep exit")
    else:
        shaft_label = "Exits slightly flat" if soft else "Exits flat"
        shaft_meaning = "the shaft points past the ball: " + ("a little flat" if soft else "a flat exit, around the body")

    # 2. Same line as the backswing (halfway back).
    back = ctx.marks.checkpoint("halfway_back")
    diff = None
    same_status = None
    back_landing = None
    if back is not None:
        back_landing, back_inside, _ = shaft_landing(ctx, back.points["clubhead"], back.points["grip"], "halfway back")
        diff = inside_by - back_inside  # + = exits more inside (steeper) than it went back
        same_status = grade(abs(diff), 0.0, cfg["same_line_max"], 0.0, cfg["same_line_watch"])
        if same_status == "ok":
            same_label, same_meaning = "Same line as the backswing", "it exits on the line it went back on"
        else:
            steeper = diff > 0
            same_label = ("Exits " + ("slightly " if same_status == "warn" else "") +
                          ("steeper" if steeper else "flatter") + " than the backswing")
            same_meaning = f"it exits on a {'steeper' if steeper else 'flatter'} line than it went back on"
        same_row = Row("Same line as backswing", f"{ctx.distance_text(diff)} {'steeper' if diff >= 0 else 'flatter'}",
                       f"{pct(abs(diff))} of torso length apart at the ball · {same_label.lower()} "
                       f"(green within ±{pct(cfg['same_line_max'])}, red past {pct(cfg['same_line_watch'])})",
                       same_status)
    else:
        same_row = Row("Same line as backswing", "–", "mark halfway back to compare the exit with the backswing", "error")

    statuses = [shaft_status] + ([same_status] if same_status else [])
    status = max(statuses, key=ORDER.__getitem__)
    label = shaft_label + (f", {same_label[0].lower() + same_label[1:]}" if same_status else "")
    summary = f"In the follow-through, {shaft_meaning}" + (f", and {same_meaning}." if same_status else ".")

    # Drawing: the shaft line carried down to the ball's level, plus where the halfway-back
    # line landed, so the two exits can be compared at the ball.
    s = ctx.scale
    show = (f, min(len(ctx.pose) - 1, f + int(round(HOLD_MS * ctx.fps / 1000))))
    col = STATUS_COLORS[shaft_status]
    overlays = [
        Overlay("segment", [tuple(clubhead), tuple(landing)], SHAFT_COLOR, "", show, 3),
        Overlay("point", [tuple(ball)], BALL_COLOR, "", show, 1),
        Overlay("point", [tuple(landing)], col, "", show, 2),
        Overlay("point", [tuple(hands)], SHAFT_COLOR, "", show, 1),
        Overlay("text", [(float(landing[0]) - toward_golfer * 0.1 * s, float(landing[1]) + 0.2 * s)], col, shaft_label, show),
    ]
    if back_landing is not None:
        same_col = STATUS_COLORS[same_status]
        overlays += [
            Overlay("point", [tuple(back_landing)], BACK_COLOR, "", show, 1),
            Overlay("segment", [tuple(back_landing), tuple(landing)], same_col, "", show, 2),
            Overlay("text", [(float(back_landing[0]) - toward_golfer * 0.1 * s, float(back_landing[1]) + 0.35 * s)],
                    BACK_COLOR, "backswing line", show),
        ]

    side = "inside" if inside_by >= 0 else "outside"
    tips = []
    if shaft_status != "ok":
        tips.append("Turn your chest through to the target and let the arms swing around you."
                    if inside_by > cfg["inside_max"] else
                    "Extend your arms up and out toward the target after impact.")
    if same_status not in (None, "ok"):
        tips.append("Match the way through to the way back: after impact the shaft should point where it did halfway back.")
    tip = " ".join(tips)

    return Verdict(
        status=status,
        label=label,
        summary=summary,
        tip=tip,
        frame=f,
        measurements={
            "shaft_inside_ball": round(inside_by, 3),
            "exit_vs_backswing": round(diff, 3) if diff is not None else None,
            "follow_through_frame": f,
            "units": "share of torso length at the ball's level; shaft: + = lands between the ball and your feet; "
                     "exit vs backswing: + = lands more inside (steeper) than at halfway back",
        },
        rows=[
            Row("Shaft points", f"{ctx.distance_text(inside_by)} {side} the ball",
                f"{pct(abs(inside_by))} of torso length · {shaft_label.lower()} "
                f"(green {pct(-cfg['inside_min'])} outside to {pct(cfg['inside_max'])} inside, "
                f"red past {pct(-cfg['inside_watch_min'])} outside or {pct(cfg['inside_watch_max'])} inside)", shaft_status),
            same_row,
            Row("Follow-through frame", str(f), "marked by you", "ok"),
        ],
        overlays=overlays,
    )
