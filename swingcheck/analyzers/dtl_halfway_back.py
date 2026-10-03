"""Down-the-line checkpoint 4: halfway back.

On the frame you mark where the lead arm is parallel to the ground, using the
clubhead and hands you click there:

  shaft points   the shaft line, from the clubhead through the hands and on
                 down to the ball's level, should land just inside the ball
                 (between the ball and your feet). Well inside = pointing at
                 your feet (shaft too steep / upright); past the ball = shaft
                 too flat (laid off).
  hands          seen from behind, the hands should "split the biceps": sit on
                 the line of the trail upper arm (shoulder to elbow, from body
                 tracking), not deep behind it or out in front of it.

Both are distances as a share of torso length, with green / yellow / red bands
in [analyzers.halfway_back].
"""

from __future__ import annotations

import numpy as np

from swingcheck.analyzers import (BALL_COLOR, REFERENCE_COLOR, STATUS_COLORS, MissingData, Overlay, Row, SwingContext,
                                  Verdict, grade, pct, register)

SHAFT_COLOR = (80, 230, 80)
HOLD_MS = 400  # how long the overlays stay up in the annotated video
ORDER = {"ok": 0, "warn": 1, "flag": 2}


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
    if hands[1] - clubhead[1] < 1:
        raise MissingData("the clubhead should be above the hands at halfway back; check the halfway-back marks")

    # Screen x direction from the ball toward the golfer (hips at address).
    hip = ctx.midpoint("left_hip", "right_hip")[ctx.marks.address_frame]
    if not np.all(np.isfinite(hip)):
        hip = ctx.value(ctx.track(ctx.side("hip", "trail")), ctx.marks.address_frame, "trail hip")
    toward_golfer = -1.0 if hip[0] < ball[0] else 1.0

    # 1. Where the shaft line, carried on down through the hands, reaches the ball's level.
    slope = (hands[0] - clubhead[0]) / (hands[1] - clubhead[1])  # screen x per screen y
    landing = np.array([hands[0] + (ball[1] - hands[1]) * slope, ball[1]])
    inside_by = ctx.units((landing[0] - ball[0]) * toward_golfer)  # + = between the ball and your feet
    shaft_status = grade(inside_by, cfg["inside_min"], cfg["inside_max"], cfg["inside_watch_min"], cfg["inside_watch_max"])
    if shaft_status == "ok":
        shaft_label, shaft_meaning = "Points just inside the ball", "the shaft points just inside the ball, on plane"
    elif inside_by > cfg["inside_max"]:
        shaft_label, shaft_meaning = (("Points well inside the ball", "the shaft points toward your feet: a little steep")
                                      if shaft_status == "warn" else
                                      ("Points at your feet", "the shaft points at your feet: too steep / upright"))
    else:
        shaft_label, shaft_meaning = (("Points just outside the ball", "the shaft points just past the ball: a little flat")
                                      if shaft_status == "warn" else
                                      ("Points outside the ball", "the shaft points well past the ball: too flat / laid off"))

    # 2. Hands vs the trail upper arm (shoulder -> elbow) at the hands' height.
    shoulder = ctx.value(ctx.track(ctx.side("shoulder", "trail")), f, "trail shoulder")
    elbow = ctx.value(ctx.track(ctx.side("elbow", "trail")), f, "trail elbow")
    if abs(elbow[1] - shoulder[1]) < 1:
        raise MissingData("the trail upper arm is level in the image, so the hands can't be compared to it")
    if hands[1] > elbow[1] + cfg["hands_below_elbow_max"] * ctx.scale:
        raise MissingData("your hands are still well below your trail elbow on the marked frame, which looks earlier "
                          "than lead arm parallel: Edit marks → Halfway back and pick a later frame")
    arm_x = shoulder[0] + (hands[1] - shoulder[1]) * (elbow[0] - shoulder[0]) / (elbow[1] - shoulder[1])
    out_by = ctx.units((hands[0] - arm_x) * -toward_golfer)  # + = toward the ball (out in front), - = behind
    lim, watch = cfg["hands_tolerance"], cfg["hands_watch"]
    hands_status = grade(out_by, -lim, lim, -watch, watch)
    if hands_status == "ok":
        hands_label, hands_meaning = "Hands split the biceps", "your hands sit on the line of your trail biceps"
    elif out_by > 0:
        hands_label, hands_meaning = (("Hands slightly in front of the arm", "your hands are a little out in front of your trail arm")
                                      if hands_status == "warn" else
                                      ("Hands far out in front of the arm", "your hands are well out in front of your trail arm, away from your body"))
    else:
        hands_label, hands_meaning = (("Hands slightly behind the arm", "your hands are a little behind your trail arm")
                                      if hands_status == "warn" else
                                      ("Hands deep behind the arm", "your hands are well behind your trail arm, pulled in deep"))

    status = max(shaft_status, hands_status, key=ORDER.__getitem__)
    label = f"{shaft_label}, {hands_label[0].lower() + hands_label[1:]}"
    summary = f"Halfway back, {shaft_meaning}, and {hands_meaning}."

    # Drawing on the marked frame: the shaft line carried down to the ball's level, the
    # ball, a tick from where it lands to the ball, and the trail upper arm with the hands.
    s = ctx.scale
    show = (f, min(len(ctx.pose) - 1, f + int(round(HOLD_MS * ctx.fps / 1000))))
    shaft_col, hands_col = STATUS_COLORS[shaft_status], STATUS_COLORS[hands_status]
    overlays = [
        Overlay("segment", [tuple(clubhead), tuple(landing)], SHAFT_COLOR, "", show, 3),
        Overlay("segment", [tuple(landing), tuple(ball)], shaft_col, "", show, 2),
        Overlay("point", [tuple(ball)], BALL_COLOR, "", show, 1),
        Overlay("point", [tuple(landing)], shaft_col, "", show, 2),
        Overlay("text", [(float(landing[0]) - toward_golfer * 0.1 * s, float(landing[1]) + 0.2 * s)], shaft_col, shaft_label, show),
        Overlay("segment", [tuple(shoulder), tuple(elbow)], REFERENCE_COLOR, "", show, 2),
        Overlay("point", [tuple(hands)], hands_col, "", show, 1),
        Overlay("point", [tuple(clubhead)], SHAFT_COLOR, "", show, 2),
        Overlay("text", [(float(hands[0]) - toward_golfer * 0.25 * s, float(hands[1]) - 0.15 * s)], hands_col, hands_label, show),
    ]

    shaft_side = "inside" if inside_by >= 0 else "outside"
    hands_side = "in front" if out_by >= 0 else "behind"
    return Verdict(
        status=status,
        label=label,
        summary=summary,
        frame=f,
        measurements={
            "shaft_inside_ball": round(inside_by, 3),
            "hands_out_from_biceps": round(out_by, 3),
            "halfway_frame": f,
            "units": "share of torso length; shaft: + = lands between the ball and your feet (inside), "
                     "- = past the ball; hands: + = out in front of the trail upper arm (toward the ball), - = behind it",
        },
        rows=[
            Row("Shaft points", f"{ctx.distance_text(inside_by)} {shaft_side} the ball",
                f"{pct(abs(inside_by))} of torso length · {shaft_label.lower()} "
                f"(green {pct(cfg['inside_min'])}–{pct(cfg['inside_max'])} inside, "
                f"red past {pct(cfg['inside_watch_max'])} inside or {pct(-cfg['inside_watch_min'])} outside)", shaft_status),
            Row("Hands vs biceps", f"{ctx.distance_text(out_by)} {hands_side}",
                f"{pct(abs(out_by))} of torso length · {hands_label.lower()} "
                f"(green within ±{pct(lim)}, red past {pct(watch)})", hands_status),
            Row("Halfway frame", str(f), "marked by you", "ok"),
        ],
        overlays=overlays,
    )
