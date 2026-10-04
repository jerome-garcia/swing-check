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
from swingcheck.analyzers import (REFERENCE_COLOR, STATUS_COLORS, MissingData, Overlay, Row, SwingContext, Verdict, grade,
                                  pct, register)
from swingcheck.geometry import angle_between_deg, max_bulge, normal, silhouette_edge, tilt_from_vertical_deg

# Back outline is sampled from this fraction of the way up the spine (skipping
# the seat, which bulges naturally) to just below the shoulder joint.
BACK_SAMPLES = np.linspace(0.2, 0.95, 24)


# (part, direction) -> how it reads when yellow, when red, and the fix.
WORDING = {
    ("arms", "out"): ("slightly reaching out", "reaching out", "Let your arms hang straight down from your shoulders."),
    ("arms", "in"): ("slightly close to body", "too close to body", "Give your hands a little more room from your body."),
    ("spine", "low"): ("slightly upright", "too upright",
                       "Hinge more from the hips: push them back and tilt forward with a straight back."),
    ("spine", "high"): ("slightly bent over", "bent over too far", "Stand up a little: tilt less from the hips."),
    ("knees", "low"): ("slightly straight", "too straight", "Soften your knees a little."),
    ("knees", "high"): ("slightly too bent", "too much bend", "Straighten your knees a little."),
    ("back", "high"): ("slightly rounded", "rounded / hump", "Keep your back straight as you tilt: chest up, no hump."),
}
GOOD = {"arms": "hanging straight", "spine": "good bend", "knees": "good flex", "back": "straight"}


def _item(part: str, status: str, direction: str) -> tuple[str, str, str]:
    """(status, note, direction) for one measurement."""
    if status == "ok":
        return status, GOOD[part], direction
    soft, hard, _ = WORDING[(part, direction)]
    return status, soft if status == "warn" else hard, direction


def _bands(lo: float, hi: float, wlo: float, whi: float) -> str:
    return f"green {lo:g}–{hi:g}°, red outside {wlo:g}–{whi:g}°"


def _deg(x: float) -> str:
    # Rounded up, so following the advice lands inside the range.
    return f"{math.ceil(round(x, 1))}°" if x >= 1 else f"{x:.1f}°"


def _adjust(value: float, lo: float, hi: float, ok_note: str, below: str, above: str) -> str:
    """Card note: what to change to get into [lo, hi], e.g. 'bend 2° more'."""
    if value < lo:
        return below.format(_deg(lo - value))
    if value > hi:
        return above.format(_deg(value - hi))
    return ok_note


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

    items: dict[str, tuple[str, str, str]] = {}  # name -> (status, note, direction)
    arm_lim, arm_watch = cfg["arm_max_from_vertical"], cfg["arm_watch_max"]
    items["arms"] = _item("arms", grade(arm, -arm_lim, arm_lim, -arm_watch, arm_watch), "out" if arm > 0 else "in")
    items["spine"] = _item("spine", grade(spine, cfg["spine_bend_min"], cfg["spine_bend_max"],
                                          cfg["spine_bend_watch_min"], cfg["spine_bend_watch_max"]),
                           "low" if spine < cfg["spine_bend_min"] else "high")
    items["knees"] = _item("knees", grade(knee_flex, cfg["knee_flex_min"], cfg["knee_flex_max"],
                                          cfg["knee_flex_watch_min"], cfg["knee_flex_watch_max"]),
                           "low" if knee_flex < cfg["knee_flex_min"] else "high")

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
        items["back"] = ("error", f"not measured ({e})", "")
    if bulge is not None:
        items["back"] = _item("back", grade(bulge, -np.inf, cfg["back_bulge_max"], -np.inf, cfg["back_bulge_watch_max"]),
                              "high")
    elif "back" not in items:
        items["back"] = ("error", "outline not found", "")

    off = {name: it for name, it in items.items() if it[0] in ("warn", "flag")}
    problems = [f"{name} {it[1]}" for name, it in off.items()]
    status = "flag" if any(it[0] == "flag" for it in off.values()) else ("warn" if off else "ok")
    label = ", ".join(problems) if problems else "good"
    # Tips lead with the hips: hinging more often fixes reaching arms too.
    tips = [WORDING[(name, off[name][2])][2] for name in ("spine", "knees", "arms", "back") if name in off]
    summary = (
        "Address posture looks good: arms hanging, spine bent, knees flexed, back straight."
        if not problems else "Address: " + "; ".join(problems) + "."
    )
    fix_tip = " ".join(tips)

    measurements = {
        "arm_from_vertical_deg": round(arm, 1),
        "spine_bend_deg": round(spine, 1),
        "knee_flex_deg": round(knee_flex, 1),
        "back_bulge": round(bulge, 3) if bulge is not None else None,
        "arms": items["arms"][1],
        "spine": items["spine"][1],
        "knees": items["knees"][1],
        "back": items["back"][1],
        "units": "angles in degrees; arm + = hands out toward ball; back bulge as a share of torso length",
    }

    show = (0, max(f, ctx.frame("takeaway")))
    col = {name: STATUS_COLORS[it[0]] for name, it in items.items()}
    s = ctx.scale
    overlays = [
        # Arm vs a vertical reference dropped from the shoulder (the dashed target
        # line below takes its place when the arms are out of range).
        *([Overlay("vline", [tuple(shoulder), (float(shoulder[0]), float(wrist[1]))], REFERENCE_COLOR, "", show, 1)]
          if items["arms"][0] not in ("warn", "flag") else []),
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
    if items["spine"][0] in ("warn", "flag"):
        aim = (cfg["spine_bend_min"] + cfg["spine_bend_max"]) / 2
        length = float(np.linalg.norm(sh_mid - hip_mid))
        tip = hip_mid + length * np.array([forward * np.sin(np.radians(aim)), -np.cos(np.radians(aim))])
        overlays.append(Overlay("dashed", [tuple(hip_mid), tuple(tip)], target, f"aim {aim:.0f} deg", show, 2))
    if items["arms"][0] in ("warn", "flag"):
        length = float(np.linalg.norm(wrist - shoulder))
        overlays.append(Overlay("dashed", [tuple(shoulder), (float(shoulder[0]), float(shoulder[1]) + length)], target,
                                "aim", show, 2))
    if items["knees"][0] in ("warn", "flag"):
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
            overlays.append(Overlay("text", [(mid[0] - forward * 0.35 * s, mid[1])], col["back"], f"back {pct(bulge)}", show))
    back_note = items["back"][1]
    if bulge is not None:
        back_note = (f"{pct(bulge)} of torso length · {back_note} "
                     f"(green up to {pct(cfg['back_bulge_max'])}, red past {pct(cfg['back_bulge_watch_max'])})")
    spine_bands = _bands(cfg["spine_bend_min"], cfg["spine_bend_max"], cfg["spine_bend_watch_min"], cfg["spine_bend_watch_max"])
    knee_bands = _bands(cfg["knee_flex_min"], cfg["knee_flex_max"], cfg["knee_flex_watch_min"], cfg["knee_flex_watch_max"])
    rows = [
        Row("Arms", f"{arm:+.1f}°", _arm_note(arm, arm_lim, arm_watch), items["arms"][0]),
        Row("Spine bend", f"{spine:.1f}°",
            _adjust(spine, cfg["spine_bend_min"], cfg["spine_bend_max"], "good bend", "bend {} more", "stand up {}")
            + f" ({spine_bands})", items["spine"][0]),
        Row("Knee flex", f"{knee_flex:.1f}°",
            _adjust(knee_flex, cfg["knee_flex_min"], cfg["knee_flex_max"], "good flex", "flex {} more", "straighten {}")
            + f" ({knee_bands})", items["knees"][0]),
        Row("Back", ctx.distance_text(bulge) if bulge is not None else "–", back_note, items["back"][0]),
    ]
    return Verdict(status=status, label=label, summary=summary, tip=fix_tip, measurements=measurements, overlays=overlays,
                   rows=rows)


def _arm_note(arm: float, limit: float, watch: float) -> str:
    bands = f"(green within ±{limit:g}°, red past ±{watch:g}°)"
    if arm > limit:
        return f"hands {_deg(arm - limit)} too far out {bands}"
    if arm < -limit:
        return f"hands {_deg(-limit - arm)} too close {bands}"
    return f"hanging straight {bands}"
