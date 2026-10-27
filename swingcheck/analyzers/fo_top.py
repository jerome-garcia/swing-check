"""Face-on checkpoint 2: top.

On the top frame you mark (the moment the club stops going back):

  back hip vs back foot  how far the back (trail) hip joint is inside the back ankle,
                         toward the target. Turning keeps it inside; sliding it out over
                         or past the back foot is a sway, which makes it hard to get back
                         to the ball.
  head vs address        how far the head center has moved along the target line since
                         address. Moving back a little is normal (pros 4-10 cm); a lot
                         is a sway of the upper body; moving toward the target is a
                         reverse pivot (the weight going the wrong way).

Distances are shares of torso length. Bands are in [analyzers.fo_top].
"""

from __future__ import annotations

import numpy as np

from swingcheck.analyzers import (Overlay, REFERENCE_COLOR, Row, STATUS_COLORS, SwingContext, Verdict, grade, register,
                                  spot_mark)
from swingcheck.analyzers.fo_impact import ORDER, _point, head_center, movement


@register("fo_top", view="fo", title="Top", phase="top")
def fo_top(ctx: SwingContext) -> Verdict:
    cfg = ctx.cfg
    sign = ctx.target_sign
    a, f = ctx.marks.address_frame, ctx.frame("top")
    trail_ankle = _point(ctx.track(ctx.side("ankle", "trail")), a, "back ankle")
    trail_hip = _point(ctx.track(ctx.side("hip", "trail")), f, "back hip")
    heads = head_center(ctx)
    head0, head1 = _point(heads, a, "head"), _point(heads, f, "head")

    # 1. Sway: + = the back hip is inside the back ankle (toward the target).
    inside = ctx.units((trail_hip[0] - trail_ankle[0]) * sign)
    sway_status = grade(inside, cfg["hip_inside_min"], np.inf, cfg["hip_inside_watch"], np.inf)
    if sway_status == "ok":
        sway_label, sway_meaning = "No sway", "your back hip stays inside your back foot"
    elif inside >= cfg["hip_inside_watch"]:
        sway_label, sway_meaning = "Slight sway", "your back hip moves out close to your back foot"
    else:
        sway_label, sway_meaning = "Swaying", "your back hip slides out past your back foot (a sway)"

    # 2. Head: + = moved toward the target since address.
    moved = ctx.units((head1[0] - head0[0]) * sign)
    head_status = grade(moved, cfg["head_back_max"], cfg["head_forward_max"], cfg["head_back_watch"],
                        cfg["head_forward_watch"])
    if head_status == "ok":
        head_label, head_meaning = "Head steady", "your head stays about where it started"
    elif moved > cfg["head_forward_max"]:
        head_label = "Head slightly toward the target" if head_status == "warn" else "Head toward the target"
        head_meaning = "your head moves toward the target as you go back (a reverse pivot)"
    else:
        head_label = "Head slightly back" if head_status == "warn" else "Head moved far back"
        head_meaning = "your head moves well back, away from the target"

    status = max(sway_status, head_status, key=ORDER.__getitem__)
    label = ("No sway, head steady" if status == "ok" else
             sway_label if sway_status == status else head_label)
    summary = f"At the top, {sway_meaning}, and {head_meaning}."
    tips = []
    if sway_status != "ok":
        tips.append("Turn your hips instead of sliding them: keep your back knee flexed and your back hip inside "
                    "your back foot as you go back.")
    if head_status != "ok":
        tips.append("Let your weight move into your back side as you turn, with your head steady or a little "
                    "back, not toward the target." if moved > cfg["head_forward_max"] else
                    "Turn around your spine: your head can drift back a little, but not this far.")

    s = ctx.scale
    show = (f, f)
    sway_col, head_col = STATUS_COLORS[sway_status], STATUS_COLORS[head_status]
    overlays = [
        Overlay("dashed", [tuple(trail_ankle), (float(trail_ankle[0]), float(trail_hip[1]) - 0.2 * s)],
                REFERENCE_COLOR, "Back foot", show, 2),
        spot_mark(trail_hip, sway_col, show, sway_label),
        *movement(ctx, "Head", head0, head1, moved, head_col, show, lift=0.22),
        spot_mark(head1, head_col, show),
    ]

    def along(value: float) -> str:
        return "toward the target" if value >= 0 else "back"

    return Verdict(
        status=status,
        label=label,
        summary=summary,
        tip=" ".join(tips),
        measurements={
            "back_hip_inside_back_ankle": round(inside, 3),
            "head_moved_toward_target": round(moved, 3),
            "top_frame": f,
            "units": "share of torso length; hip: + = inside the back ankle; head: + = toward the target",
        },
        rows=[
            Row("Back hip vs back foot", f"{ctx.distance_text(inside)} {'inside' if inside >= 0 else 'outside'}",
                sway_label, sway_status,
                good=f"{ctx.distance_text(cfg['hip_inside_min'])} or more inside your back foot",
                fix="outside your back foot"),
            Row("Head vs address", "Same place" if abs(ctx.cm(moved)) < 0.75 else
                f"{ctx.distance_text(moved)} {along(moved)}", head_label, head_status,
                good=f"up to {ctx.distance_text(-cfg['head_back_max'])} back, or "
                     f"{ctx.distance_text(cfg['head_forward_max'])} toward the target",
                fix=f"more than {ctx.distance_text(-cfg['head_back_watch'])} back, or "
                    f"{ctx.distance_text(cfg['head_forward_watch'])} toward the target"),
        ],
        overlays=overlays,
    )
