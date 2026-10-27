"""Face-on checkpoint 4: impact.

On the impact frame the golfer confirms while marking, with their hands clicked there
(tracked wrists are often a blur at impact) and the ball clicked at address:

  hands vs ball   how far the hands are ahead of the ball, toward the target. Ahead
                  means the shaft leans forward; behind means it leans back (a scoop),
                  which adds loft and moves the low point back: fat and high shots.
                  With a driver the ball sits forward and is hit on the way up, so the
                  hands are level with it or a little behind: a watch item only.
  hips vs address how far the hip center has moved toward the target since address.
                  Not getting the hips forward leaves the low point behind the ball.
  head vs ball    where the head center (nose and ears) is against the ball. Behind or
                  over it is good; well past it (toward the target) means lunging; far
                  behind means hanging back, a watch item only.

Distances are shares of torso length, + = toward the target. Bands are in
[analyzers.fo_impact] (driver ones in [clubs.driver.analyzers.fo_impact]).
"""

from __future__ import annotations

import warnings

import numpy as np

from swingcheck.analyzers import (MissingData, Overlay, REFERENCE_COLOR, Row, STATUS_COLORS, SwingContext, Verdict,
                                  WATCH_ONLY, grade, hands_mark, register, spot_mark, watch_at_most)

ORDER = {"ok": 0, "warn": 1, "flag": 2}
HOLD_MS = 300
HEAD_POINTS = ("nose", "left_ear", "right_ear")


def head_center(ctx: SwingContext) -> np.ndarray:
    """The head's center: the mean of nose and ears, steadier than the nose alone as the head turns."""
    tracks = np.stack([ctx.track(name) for name in HEAD_POINTS])  # (3, frames, 2)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # frames with none tracked stay NaN
        return np.nanmean(tracks, axis=0)


def _point(track: np.ndarray, frame: int, what: str, look_back: int = 0) -> np.ndarray:
    """The track on this frame, or (with look_back) the nearest tracked frame up to that
    many before it: a finish held to the clip's last frame can lose tracking there."""
    for f in range(frame, max(-1, frame - look_back - 1), -1):
        if np.all(np.isfinite(track[f])):
            return track[f]
    raise MissingData(f"Your {what} wasn't tracked on frame {frame}.")


@register("fo_impact", view="fo", title="Impact", phase="impact")
def fo_impact(ctx: SwingContext) -> Verdict:
    cfg = ctx.cfg
    sign = ctx.target_sign  # +1: the target is screen-right
    a, f = ctx.marks.address_frame, ctx.frame("impact")
    ball = np.asarray(ctx.marks.points["ball"], float)
    mark = ctx.marks.checkpoint("impact")
    if mark is None or "grip" not in mark.points:
        raise MissingData("Click your hands on the Impact step (Edit marks).")
    hands = np.asarray(mark.points["grip"], float)
    hips = ctx.midpoint("left_hip", "right_hip")
    hip0, hip1 = _point(hips, a, "hips"), _point(hips, f, "hips")
    head = _point(head_center(ctx), f, "head")

    # 1. Hands vs ball.
    ahead = ctx.units((hands[0] - ball[0]) * sign)
    hands_status = grade(ahead, cfg["hands_ahead_min"], np.inf, cfg["hands_ahead_watch"], np.inf)
    if cfg["hands_watch_only"]:
        hands_status = watch_at_most(hands_status)
    if hands_status == "ok":
        hands_label, hands_meaning = "Hands ahead of the ball", "your hands are ahead of the ball (the shaft leans forward)"
    elif ahead >= cfg["hands_ahead_watch"]:
        hands_label, hands_meaning = "Hands about level with the ball", "your hands are about level with the ball"
    else:
        hands_label, hands_meaning = ("Hands behind the ball",
                                      "your hands are behind the ball (the shaft leans back: a scoop)")

    # 2. Hips vs address.
    shift = ctx.units((hip1[0] - hip0[0]) * sign)
    hips_status = grade(shift, cfg["hips_shift_min"], np.inf, cfg["hips_shift_watch"], np.inf)
    if hips_status == "ok":
        hips_label, hips_meaning = "Hips moved forward", "your hips have moved toward the target"
    elif shift >= 0:
        hips_label, hips_meaning = "Hips barely moved forward", "your hips have only just moved toward the target"
    else:
        hips_label, hips_meaning = "Hips moved back", "your hips have moved away from the target (hanging back)"

    # 3. Head vs ball: + = behind the ball (away from the target).
    behind = ctx.units((ball[0] - head[0]) * sign)
    head_band = grade(behind, cfg["head_ahead_max"], cfg["head_behind_max"],
                      cfg["head_ahead_watch"], cfg["head_behind_max"])
    head_status = head_band if behind < cfg["head_ahead_max"] else watch_at_most(head_band)  # far back: watch only
    if head_status == "ok":
        head_label, head_meaning = "Head behind the ball", "your head stays behind the ball"
    elif behind < cfg["head_ahead_max"]:
        head_label = "Head slightly past the ball" if head_status == "warn" else "Head past the ball"
        head_meaning = ("your head has moved a little past the ball" if head_status == "warn" else
                        "your head has moved past the ball toward the target (lunging)")
    else:
        head_label, head_meaning = "Head well behind the ball", "your head hangs well back behind the ball"

    status = max(hands_status, hips_status, head_status, key=ORDER.__getitem__)
    # The headline: the worst row (the first, in this order, if two tie), or all three when green.
    label = ("Hands ahead, hips forward, head behind the ball" if status == "ok" else
             next(lab for st, lab in ((hands_status, hands_label), (hips_status, hips_label), (head_status, head_label))
                  if st == status))
    summary = f"At impact, {hands_meaning}, {hips_meaning}, and {head_meaning}."

    tips = []
    if hands_status != "ok" and not cfg["hands_watch_only"]:
        tips.append("Lead with your hands: at impact they should be ahead of the ball, toward the target, with "
                    "the shaft leaning forward. Don't flip the clubhead past them.")
    if hips_status != "ok":
        tips.append("Start the downswing by shifting your weight onto your front foot, so your hips are toward "
                    "the target by impact.")
    if head_status != "ok":
        tips.append("Keep your head behind the ball through impact instead of sliding it toward the target."
                    if behind < cfg["head_ahead_max"] else
                    "Let your weight move to your front side; your head can stay back, but not this far.")

    # Drawing on the impact frame: a line up from the ball, the hands, the hip center now
    # and at address, and the head.
    s = ctx.scale
    show = (f, min(len(ctx.pose) - 1, f + int(round(HOLD_MS * ctx.fps / 1000))))
    hips_col, head_col = STATUS_COLORS[hips_status], STATUS_COLORS[head_status]
    overlays = [
        Overlay("dashed", [tuple(ball), (float(ball[0]), float(head[1]) - 0.2 * s)], REFERENCE_COLOR, "Ball", show, 2),
        spot_mark(ball, REFERENCE_COLOR, show),
        hands_mark(hands, STATUS_COLORS[hands_status], show, hands_label),
        Overlay("vline", [(float(hip0[0]), float(hip0[1]) - 0.3 * s), (float(hip0[0]), float(hip0[1]) + 0.3 * s)],
                REFERENCE_COLOR, "", show, 2),
        Overlay("segment", [(float(hip0[0]), float(hip1[1])), tuple(hip1)], hips_col, "", show, 3),
        Overlay("text", [(float(hip1[0]), float(hip1[1]) - 0.35 * s)], hips_col, hips_label, show),
        spot_mark(head, head_col, show, head_label),
    ]

    def toward(value: float) -> str:
        return "toward the target" if value >= 0 else "away from the target"

    hands_fix = (WATCH_ONLY if cfg["hands_watch_only"]
                 else f"more than {ctx.distance_text(-cfg['hands_ahead_watch'])} behind the ball")
    return Verdict(
        status=status,
        label=label,
        summary=summary,
        tip=" ".join(tips),
        measurements={
            "hands_ahead_of_ball": round(ahead, 3),
            "hips_toward_target": round(shift, 3),
            "head_behind_ball": round(behind, 3),
            "impact_frame": f,
            "units": "share of torso length; hands and hips: + = toward the target; head: + = behind the ball",
        },
        rows=[
            Row("Hands vs ball", "Level" if abs(ctx.cm(ahead)) < 0.75 else
                f"{ctx.distance_text(ahead)} {'ahead' if ahead > 0 else 'behind'}",
                hands_label.removeprefix("Hands ").capitalize(), hands_status,
                good=(f"{ctx.distance_text(cfg['hands_ahead_min'])} or more ahead" if cfg["hands_ahead_min"] > 0 else
                      f"level, or up to {ctx.distance_text(-cfg['hands_ahead_min'])} behind, or ahead"),
                fix=hands_fix),
            Row("Hips vs address", f"{ctx.distance_text(shift)} {toward(shift)}",
                hips_label.removeprefix("Hips ").capitalize(), hips_status,
                good=f"{ctx.distance_text(cfg['hips_shift_min'])} or more toward the target",
                fix="moved away from the target"),
            Row("Head vs ball", f"{ctx.distance_text(behind)} {'behind' if behind >= 0 else 'past'} the ball",
                head_label.removeprefix("Head ").capitalize(), head_status,
                good=f"up to {ctx.distance_text(-cfg['head_ahead_max'])} past, to "
                     f"{ctx.distance_text(cfg['head_behind_max'])} behind",
                fix=f"more than {ctx.distance_text(-cfg['head_ahead_watch'])} past the ball"),
        ],
        overlays=overlays,
    )
