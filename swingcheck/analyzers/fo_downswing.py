"""Face-on checkpoint 3: downswing.

On the downswing frame you mark (the shaft parallel to the ground on the way down):

  hips vs address  how far the hip center has moved toward the target since address.
                   The downswing starts with the lower body: by now the hips should be
                   well on their way (pros 10-17 cm).
  head vs address  how far the head has moved along the target line since address. It
                   stays back while the hips move; sliding it toward the target throws
                   the low point forward and the club steep.

Distances are shares of torso length. Bands are in [analyzers.fo_downswing].
"""

from __future__ import annotations

import numpy as np

from swingcheck.analyzers import MissingData, Row, STATUS_COLORS, SwingContext, Verdict, grade, register, spot_mark
from swingcheck.analyzers.fo_impact import ORDER, _point, head_center, movement


@register("fo_downswing", view="fo", title="Downswing")
def fo_downswing(ctx: SwingContext) -> Verdict:
    mark = ctx.marks.checkpoint("downswing")
    if mark is None:
        raise MissingData("Downswing isn't marked yet. Go to Edit marks → Downswing and pick the frame.")
    cfg = ctx.cfg
    sign = ctx.target_sign
    a, f = ctx.marks.address_frame, mark.frame
    hips = ctx.midpoint("left_hip", "right_hip")
    hip0, hip1 = _point(hips, a, "hips"), _point(hips, f, "hips")
    heads = head_center(ctx)
    head0, head1 = _point(heads, a, "head"), _point(heads, f, "head")

    shift = ctx.units((hip1[0] - hip0[0]) * sign)
    hips_status = grade(shift, cfg["hips_shift_min"], np.inf, cfg["hips_shift_watch"], np.inf)
    if hips_status == "ok":
        hips_label, hips_meaning = "Hips leading", "your hips have moved toward the target"
    elif shift >= cfg["hips_shift_watch"]:
        hips_label, hips_meaning = "Hips slow to move", "your hips have only moved a little toward the target"
    else:
        hips_label, hips_meaning = "Hips not moving", "your hips haven't moved toward the target"

    moved = ctx.units((head1[0] - head0[0]) * sign)
    head_status = grade(moved, cfg["head_back_max"], cfg["head_forward_max"], -np.inf, cfg["head_forward_watch"])
    if head_status == "ok":
        head_label, head_meaning = "Head staying back", "your head stays back"
    else:
        head_label = "Head moving forward" if head_status == "warn" else "Head lunging forward"
        head_meaning = "your head has moved toward the target ahead of your hips"

    status = max(hips_status, head_status, key=ORDER.__getitem__)
    label = ("Hips leading, head back" if status == "ok" else
             hips_label if hips_status == status else head_label)
    summary = f"On the way down, {hips_meaning}, and {head_meaning}."
    tips = []
    if hips_status != "ok":
        tips.append("Start the downswing from the ground up: shift your weight onto your front foot so your hips "
                    "move toward the target before your arms swing down.")
    if head_status != "ok":
        tips.append("Keep your head back while your hips move forward; let it go toward the target only after "
                    "the ball is gone.")

    show = (f, f)
    hips_col, head_col = STATUS_COLORS[hips_status], STATUS_COLORS[head_status]
    overlays = [
        *movement(ctx, "Hips", hip0, hip1, shift, hips_col, show),
        *movement(ctx, "Head", head0, head1, moved, head_col, show, lift=0.22),
        spot_mark(head1, head_col, show),
    ]
    return Verdict(
        status=status,
        label=label,
        frame=f,  # the marked frame: its key frame (it has no detected phase of its own)
        summary=summary,
        tip=" ".join(tips),
        measurements={
            "hips_toward_target": round(shift, 3),
            "head_moved_toward_target": round(moved, 3),
            "downswing_frame": f,
            "units": "share of torso length since address, + = toward the target",
        },
        rows=[
            Row("Hips vs address", f"{ctx.distance_text(shift)} {'toward the target' if shift >= 0 else 'back'}",
                hips_label, hips_status,
                good=f"{ctx.distance_text(cfg['hips_shift_min'])} or more toward the target",
                fix=f"under {ctx.distance_text(cfg['hips_shift_watch'])}"),
            Row("Head vs address", "Same place" if abs(ctx.cm(moved)) < 0.75 else
                f"{ctx.distance_text(moved)} {'toward the target' if moved >= 0 else 'back'}",
                head_label, head_status,
                good=f"up to {ctx.distance_text(cfg['head_forward_max'])} toward the target, or back",
                fix=f"more than {ctx.distance_text(cfg['head_forward_watch'])} toward the target"),
        ],
        overlays=overlays,
    )
