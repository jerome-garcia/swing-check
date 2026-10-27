"""Face-on checkpoint 5: finish.

On the finish frame you mark (the swing over, holding the pose):

  hips vs address        how far the hip center has moved toward the target since
                         address. A full finish has the weight on the front side (pros
                         11-25 cm); hips still at or behind where they started mean you
                         finished on your back foot.
  head vs front foot     where the head center is against the front ankle. Over or near
                         the front foot is balanced; far behind it means hanging back, far
                         past it means falling forward.

Both are watch items at most, never Fix (like the follow-through down the line): the ball
is gone by now, finishes vary, and they mostly show what came before. Distances are shares of torso length. Bands are in [analyzers.fo_finish].
"""

from __future__ import annotations

import numpy as np

from swingcheck.analyzers import (MissingData, Overlay, REFERENCE_COLOR, Row, STATUS_COLORS, SwingContext, Verdict,
                                  WATCH_ONLY, grade, register, spot_mark, watch_at_most)
from swingcheck.analyzers.fo_impact import ORDER, _point, head_center, movement


@register("fo_finish", view="fo", title="Finish")
def fo_finish(ctx: SwingContext) -> Verdict:
    mark = ctx.marks.checkpoint("finish")
    if mark is None:
        raise MissingData("Finish isn't marked yet. Go to Edit marks → Finish and pick the frame.")
    cfg = ctx.cfg
    sign = ctx.target_sign
    a, f = ctx.marks.address_frame, mark.frame
    back = int(round(0.15 * ctx.fps))  # the pose is held, so a frame or two earlier is the same
    hips = ctx.midpoint("left_hip", "right_hip")
    hip0, hip1 = _point(hips, a, "hips"), _point(hips, f, "hips", back)
    lead_ankle = _point(ctx.track(ctx.side("ankle", "lead")), a, "front ankle")
    head = _point(head_center(ctx), f, "head", back)

    shift = ctx.units((hip1[0] - hip0[0]) * sign)
    hips_status = watch_at_most(grade(shift, cfg["hips_shift_min"], np.inf, cfg["hips_shift_watch"], np.inf))
    if hips_status == "ok":
        hips_label, hips_meaning = "Weight on the front side", "your weight has moved onto your front side"
    elif shift >= cfg["hips_shift_watch"]:
        hips_label, hips_meaning = "Weight partly forward", "only part of your weight has moved onto your front side"
    else:
        hips_label, hips_meaning = "Finishing on the back foot", "you finish with your weight on your back foot"

    past = ctx.units((head[0] - lead_ankle[0]) * sign)  # + = past the front ankle, toward the target
    head_status = watch_at_most(grade(past, cfg["head_behind_max"], cfg["head_past_max"], -np.inf, np.inf))
    if head_status == "ok":
        head_label, head_meaning = "Head over the front foot", "your head is over your front foot"
    elif past < cfg["head_behind_max"]:
        head_label, head_meaning = "Head well behind the front foot", "your head stays well back"
    else:
        head_label, head_meaning = "Head past the front foot", "your head has gone past your front foot"

    status = max(hips_status, head_status, key=ORDER.__getitem__)
    label = ("Balanced on the front side" if status == "ok" else
             hips_label if hips_status == status else head_label)
    summary = f"At the finish, {hips_meaning}, and {head_meaning}."
    tips = []
    if hips_status != "ok":
        tips.append("Swing through to a full finish with your weight on your front foot, your back heel up, and "
                    "your belt buckle facing the target.")
    if head_status != "ok":
        tips.append("Finish tall and balanced, with your head over your front foot."
                    if past < cfg["head_behind_max"] else "Hold your finish without falling toward the target.")

    s = ctx.scale
    show = (f, f)
    hips_col, head_col = STATUS_COLORS[hips_status], STATUS_COLORS[head_status]
    overlays = [
        Overlay("dashed", [tuple(lead_ankle), (float(lead_ankle[0]), float(head[1]) - 0.2 * s)],
                REFERENCE_COLOR, "Front foot", show, 2),
        *movement(ctx, "Hips", hip0, hip1, shift, hips_col, show),
        spot_mark(head, head_col, show, head_label),
    ]
    return Verdict(
        status=status,
        label=label,
        frame=f,  # the marked frame: its key frame (it has no detected phase of its own)
        summary=summary,
        tip=" ".join(tips),
        measurements={
            "hips_toward_target": round(shift, 3),
            "head_past_front_ankle": round(past, 3),
            "finish_frame": f,
            "units": "share of torso length; hips: since address, + = toward the target; "
                     "head: + = past the front ankle",
        },
        rows=[
            Row("Hips vs address", f"{ctx.distance_text(shift)} {'toward the target' if shift >= 0 else 'back'}",
                hips_label, hips_status,
                good=f"{ctx.distance_text(cfg['hips_shift_min'])} or more toward the target",
                fix=WATCH_ONLY),
            Row("Head vs front foot", f"{ctx.distance_text(past)} {'past' if past >= 0 else 'behind'}",
                head_label, head_status,
                good=f"{ctx.distance_text(-cfg['head_behind_max'])} behind to "
                     f"{ctx.distance_text(cfg['head_past_max'])} past",
                fix=WATCH_ONLY),
        ],
        overlays=overlays,
    )
