"""Down-the-line: address posture on the frame you marked.

Uses the camera-side (trail side) body points, which are the ones clearly
visible from behind:

  arms        shoulder -> wrist line vs vertical (arms should hang straight down)
  spine       hip center -> shoulder center, forward bend from vertical
  knees       knee flex = 180 - hip-knee-ankle angle
  back        how far the outline of the back bulges beyond a straight line
              between hip and shoulder level (from the body silhouette)
"""

from __future__ import annotations

import numpy as np

from swingcheck import pose as pose_mod
from swingcheck.analyzers import REFERENCE_COLOR, STATUS_COLORS, MissingData, Overlay, SwingContext, Verdict, register
from swingcheck.geometry import angle_between_deg, max_bulge, normal, silhouette_edge, tilt_from_vertical_deg

# Back outline is sampled from this fraction of the way up the spine (skipping
# the seat, which bulges naturally) to just below the shoulder joint.
BACK_SAMPLES = np.linspace(0.2, 0.95, 24)


def _status(ok: bool) -> str:
    return "ok" if ok else "flag"


@register("address", view="dtl", title="Address posture")
def address(ctx: SwingContext) -> Verdict:
    cfg = ctx.cfg
    f = ctx.marks.address_frame
    trail = lambda part: ctx.track(ctx.side(part, "trail"))  # noqa: E731

    shoulder = ctx.value(trail("shoulder"), f, "trail shoulder")
    wrist = ctx.value(trail("wrist"), f, "trail wrist")
    hip = ctx.value(trail("hip"), f, "trail hip")
    knee = ctx.value(trail("knee"), f, "trail knee")
    ankle = ctx.value(trail("ankle"), f, "trail ankle")
    # Spine from body centers when both sides are tracked; trail side otherwise.
    sh_mid = ctx.midpoint("left_shoulder", "right_shoulder")[f]
    hip_mid = ctx.midpoint("left_hip", "right_hip")[f]
    if not (np.all(np.isfinite(sh_mid)) and np.all(np.isfinite(hip_mid))):
        sh_mid, hip_mid = shoulder, hip

    # The golfer faces the ball: "forward" is from the hips toward the ball.
    forward = 1 if ctx.marks.points["ball"][0] >= hip[0] else -1

    arm = tilt_from_vertical_deg(wrist - shoulder, forward)          # + = hands reaching toward the ball
    spine = tilt_from_vertical_deg(sh_mid - hip_mid, forward, up=True)  # + = bent toward the ball
    knee_flex = 180.0 - angle_between_deg(hip - knee, ankle - knee)

    items: dict[str, tuple[str, str]] = {}  # name -> (status, note)
    arm_ok = abs(arm) <= cfg["arm_max_from_vertical"]
    items["arms"] = (_status(arm_ok), "hanging straight" if arm_ok else ("reaching out" if arm > 0 else "too close to body"))
    spine_ok = cfg["spine_bend_min"] <= spine <= cfg["spine_bend_max"]
    items["spine"] = (_status(spine_ok), "good bend" if spine_ok else ("too upright" if spine < cfg["spine_bend_min"] else "bent over too far"))
    knee_ok = cfg["knee_flex_min"] <= knee_flex <= cfg["knee_flex_max"]
    items["knees"] = (_status(knee_ok), "good flex" if knee_ok else ("too straight" if knee_flex < cfg["knee_flex_min"] else "too much bend"))

    # Back outline from the silhouette. Outward = away from the ball, across the spine.
    back_points = np.empty((0, 2))
    bulge = None
    outward = normal(sh_mid - hip_mid)
    if outward[0] * forward > 0:
        outward = -outward
    try:
        mask = pose_mod.segment_frame(ctx.image(f), ctx.config)
        back_points = silhouette_edge(mask, hip_mid, sh_mid, outward, BACK_SAMPLES, max_reach_px=0.6 * ctx.scale)
        bulge_px = max_bulge(back_points, outward)
        if np.isfinite(bulge_px):
            bulge = ctx.units(bulge_px)
    except (MissingData, RuntimeError) as e:
        items["back"] = ("error", f"not measured ({e})")
    if bulge is not None:
        back_ok = bulge <= cfg["back_bulge_max"]
        items["back"] = (_status(back_ok), "straight" if back_ok else "rounded / hump")
    elif "back" not in items:
        items["back"] = ("error", "outline not found")

    problems = [f"{name} {note}" for name, (st, note) in items.items() if st == "flag"]
    status = "flag" if problems else "ok"
    label = ", ".join(problems) if problems else "good"
    summary = (
        "Address posture looks good: arms hanging, spine bent, knees flexed, back straight."
        if not problems else "Address: " + "; ".join(problems) + "."
    )

    measurements = {
        "arm_from_vertical_deg": round(arm, 1),
        "spine_bend_deg": round(spine, 1),
        "knee_flex_deg": round(knee_flex, 1),
        "back_bulge": round(bulge, 3) if bulge is not None else None,
        "arms": items["arms"][1],
        "spine": items["spine"][1],
        "knees": items["knees"][1],
        "back": items["back"][1],
        "units": "angles in degrees; arm + = hands out toward ball; back bulge in body lengths",
    }

    show = (0, max(f, ctx.frame("takeaway")))
    col = {name: STATUS_COLORS[st] for name, (st, _) in items.items()}
    s = ctx.scale
    overlays = [
        # Arm vs a vertical reference dropped from the shoulder.
        Overlay("vline", [tuple(shoulder), (float(shoulder[0]), float(wrist[1]))], REFERENCE_COLOR, "", show, 1),
        Overlay("segment", [tuple(shoulder), tuple(wrist)], col["arms"], "", show, 3),
        Overlay("text", [(float(wrist[0]) + 0.08 * s, float(wrist[1]))], col["arms"], f"arm {arm:+.0f} deg", show),
        # Spine line with its angle.
        Overlay("segment", [tuple(hip_mid), tuple(sh_mid)], col["spine"], "", show, 3),
        Overlay("text", [tuple((hip_mid + sh_mid) / 2 + forward * np.array([0.12 * s, 0.0]))], col["spine"],
                f"spine {spine:.0f} deg", show),
        # Leg with knee flex.
        Overlay("polyline", [tuple(hip), tuple(knee), tuple(ankle)], col["knees"], "", show, 3),
        Overlay("text", [(float(knee[0]) + forward * 0.1 * s, float(knee[1]))], col["knees"], f"knee {knee_flex:.0f} deg", show),
    ]
    if len(back_points) and np.isfinite(back_points).any():
        pts = [tuple(p) for p in back_points if np.all(np.isfinite(p))]
        overlays.append(Overlay("polyline", pts, col["back"], "", show, 2))
        overlays.append(Overlay("segment", [pts[0], pts[-1]], REFERENCE_COLOR, "", show, 1))
        if bulge is not None:
            mid = pts[len(pts) // 2]
            overlays.append(Overlay("text", [(mid[0] - forward * 0.35 * s, mid[1])], col["back"], f"back {bulge:.2f}", show))
    return Verdict(status=status, label=label, summary=summary, measurements=measurements, overlays=overlays)
