"""Down-the-line: address posture on the frame you marked.

Uses the camera-side (trail side) body points, which are the ones clearly
visible from behind:

  arms        shoulder -> wrist line vs vertical (arms should hang straight down)
  spine       hip center -> shoulder center, forward bend from vertical
  knees       knee flex = 180 - hip-knee-ankle angle
  back        how far the outline of the back bulges beyond a straight line
              between hip and shoulder level (from the body silhouette)

For anything out of range, the card says how far and which way to move, and
the key frame draws a dashed target line at the middle of the good range.
"""

from __future__ import annotations

import math

import numpy as np

from swingcheck import pose as pose_mod
from swingcheck.analyzers import REFERENCE_COLOR, STATUS_COLORS, MissingData, Overlay, Row, SwingContext, Verdict, register
from swingcheck.geometry import angle_between_deg, max_bulge, normal, silhouette_edge, tilt_from_vertical_deg

# Back outline is sampled from this fraction of the way up the spine (skipping
# the seat, which bulges naturally) to just below the shoulder joint.
BACK_SAMPLES = np.linspace(0.2, 0.95, 24)


TIPS = {
    ("spine", "too upright"): "Hinge more from the hips: push them back and tilt forward with a straight back.",
    ("spine", "bent over too far"): "Stand up a little: tilt less from the hips.",
    ("knees", "too straight"): "Soften your knees a little.",
    ("knees", "too much bend"): "Straighten your knees a little.",
    ("arms", "reaching out"): "Let your arms hang straight down from your shoulders.",
    ("arms", "too close to body"): "Give your hands a little more room from your body.",
    ("back", "rounded / hump"): "Keep your back straight as you tilt: chest up, no hump.",
}


def _status(ok: bool) -> str:
    return "ok" if ok else "flag"


def _deg(x: float) -> str:
    # Rounded up, so following the advice lands inside the range.
    return f"{math.ceil(round(x, 1))}°" if x >= 1 else f"{x:.1f}°"


def _adjust(value: float, lo: float, hi: float, ok_note: str, below: str, above: str) -> str:
    """Card note: what to change to get into [lo, hi], e.g. 'bend 1° more (30–45°)'."""
    rng = f"({lo:g}–{hi:g}°)"
    if value < lo:
        return f"{below.format(_deg(lo - value))} {rng}"
    if value > hi:
        return f"{above.format(_deg(value - hi))} {rng}"
    return f"{ok_note} {rng}"


def _rotate(v: np.ndarray, deg: float) -> np.ndarray:
    a = np.radians(deg)
    return np.array([np.cos(a) * v[0] - np.sin(a) * v[1], np.sin(a) * v[0] + np.cos(a) * v[1]])


@register("address", view="dtl", title="Address posture", phase="address")
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
    # Tips lead with the hips: hinging more often fixes reaching arms too.
    tips = [TIPS[(name, items[name][1])] for name in ("spine", "knees", "arms", "back")
            if items[name][0] == "flag" and (name, items[name][1]) in TIPS]
    summary = (
        "Address posture looks good: arms hanging, spine bent, knees flexed, back straight."
        if not problems else " ".join(tips) or "Address: " + "; ".join(problems) + "."
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
        # Arm vs a vertical reference dropped from the shoulder (the dashed target
        # line below takes its place when the arms are out of range).
        *([Overlay("vline", [tuple(shoulder), (float(shoulder[0]), float(wrist[1]))], REFERENCE_COLOR, "", show, 1)]
          if items["arms"][0] != "flag" else []),
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
    # Dashed target lines (middle of the good range) for whatever is out of range.
    target = STATUS_COLORS["ok"]
    if items["spine"][0] == "flag":
        aim = (cfg["spine_bend_min"] + cfg["spine_bend_max"]) / 2
        length = float(np.linalg.norm(sh_mid - hip_mid))
        tip = hip_mid + length * np.array([forward * np.sin(np.radians(aim)), -np.cos(np.radians(aim))])
        overlays.append(Overlay("dashed", [tuple(hip_mid), tuple(tip)], target, f"aim {aim:.0f} deg", show, 2))
    if items["arms"][0] == "flag":
        length = float(np.linalg.norm(wrist - shoulder))
        overlays.append(Overlay("dashed", [tuple(shoulder), (float(shoulder[0]), float(shoulder[1]) + length)], target,
                                "aim", show, 2))
    if items["knees"][0] == "flag":
        # Shin stays put; the thigh swings to the target flex (hip behind the knee).
        aim = (cfg["knee_flex_min"] + cfg["knee_flex_max"]) / 2
        shin = (ankle - knee) / np.linalg.norm(ankle - knee)
        thigh_len = float(np.linalg.norm(hip - knee))
        options = [knee + thigh_len * _rotate(shin, sign * (180.0 - aim)) for sign in (1, -1)]
        hip_aim = min(options, key=lambda p: (p[0] - knee[0]) * forward)
        overlays.append(Overlay("dashed", [tuple(knee), tuple(hip_aim)], target, f"aim {aim:.0f} deg", show, 2))
    if len(back_points) and np.isfinite(back_points).any():
        pts = [tuple(p) for p in back_points if np.all(np.isfinite(p))]
        overlays.append(Overlay("polyline", pts, col["back"], "", show, 2))
        overlays.append(Overlay("segment", [pts[0], pts[-1]], REFERENCE_COLOR, "", show, 1))
        if bulge is not None:
            mid = pts[len(pts) // 2]
            overlays.append(Overlay("text", [(mid[0] - forward * 0.35 * s, mid[1])], col["back"], f"back {bulge:.2f}", show))
    rows = [
        Row("Arms", f"{arm:+.1f}°", _arm_note(arm, cfg["arm_max_from_vertical"]), items["arms"][0]),
        Row("Spine bend", f"{spine:.1f}°", _adjust(spine, cfg["spine_bend_min"], cfg["spine_bend_max"],
                                                   "good bend", "bend {} more", "stand up {}"), items["spine"][0]),
        Row("Knee flex", f"{knee_flex:.1f}°", _adjust(knee_flex, cfg["knee_flex_min"], cfg["knee_flex_max"],
                                                     "good flex", "flex {} more", "straighten {}"), items["knees"][0]),
        Row("Back", f"{bulge:.3f}" if bulge is not None else "–", items["back"][1], items["back"][0]),
    ]
    return Verdict(status=status, label=label, summary=summary, measurements=measurements, overlays=overlays,
                   rows=rows)


def _arm_note(arm: float, limit: float) -> str:
    rng = f"(within ±{limit:g}°)"
    if arm > limit:
        return f"hands {_deg(arm - limit)} too far out {rng}"
    if arm < -limit:
        return f"hands {_deg(-limit - arm)} too close {rng}"
    return f"hanging straight {rng}"
