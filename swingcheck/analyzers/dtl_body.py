"""Body kept from address: spine bend and trail knee flex, shared by the
down-the-line takeaway (3) and halfway back (4) checks.

From tracking only, no extra marks. Each check reads its bands from its own
config section: posture_loss_max / posture_loss_watch / posture_gain_max /
posture_gain_watch (degrees of spine bend) and knee_straighten_max /
knee_straighten_watch / knee_bend_max / knee_bend_watch (degrees of trail knee
flex). A body point not tracked on either frame gives a "not measured" row that
doesn't count toward the check's result. Not a checkpoint: registers nothing.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from swingcheck.analyzers import REFERENCE_COLOR, STATUS_COLORS, Grade, Overlay, Row, SwingContext, deg_text, grade
from swingcheck.geometry import angle_between_deg, tilt_from_vertical_deg

ORDER = {"ok": 0, "warn": 1, "flag": 2}


@dataclass
class BodyCheck:
    status: str
    label: str  # "" when ok or not measured
    meaning: str
    tip: str
    row: Row
    overlays: list[Overlay]



def list_text(items: list[str]) -> str:
    """"a", "a and b", "a, b, and c" (with the Oxford comma, as all SwingCheck text)."""
    return " and ".join(items) if len(items) <= 2 else f"{', '.join(items[:-1])}, and {items[-1]}"


def with_body(status: str, label: str, meaning: str, tip: str, body: list[BodyCheck]) -> tuple[str, str, str, str]:
    """A check's result with its body rows folded in: the worst status, faults appended
    to the label and the summary sentence, and their tips added."""
    status = max([status] + [b.status for b in body], key=ORDER.__getitem__)
    faults = [b for b in body if b.label]
    if faults:
        label = ", ".join([label] + [b.label[0].lower() + b.label[1:] for b in faults])
        meaning = f"{meaning} Your {list_text([b.meaning for b in faults])}."
    tip = " ".join(t for t in [tip] + [b.tip for b in body] if t)
    return status, label, meaning, tip


def _either_way(a: float, a_word: str, b: float, b_word: str, lead: str) -> str:
    """'up to 6° more upright or 5° more bent'; 'more than 10° either way' when both match."""
    if a == b:
        return f"{lead} {a:g}° either way"
    return f"{lead} {a:g}° {a_word} or {b:g}° {b_word}"


def posture_kept(ctx: SwingContext, f: int, forward: float, show: tuple[int, int]) -> BodyCheck:
    """Spine bend on frame f vs address; lost = standing up."""
    cfg = ctx.cfg
    a = ctx.marks.address_frame
    hip0, sh0 = ctx.midpoint("left_hip", "right_hip")[a], ctx.midpoint("left_shoulder", "right_shoulder")[a]
    hip1, sh1 = ctx.midpoint("left_hip", "right_hip")[f], ctx.midpoint("left_shoulder", "right_shoulder")[f]
    if not all(np.all(np.isfinite(p)) for p in (hip0, sh0, hip1, sh1)):
        return BodyCheck("ok", "", "", "", Row("Spine bend kept", "Not measured",
                         "Hips or shoulders not tracked on the address frame or this one", "error"), [])
    bend0 = tilt_from_vertical_deg(sh0 - hip0, forward, up=True)
    bend1 = tilt_from_vertical_deg(sh1 - hip1, forward, up=True)
    lost = bend0 - bend1  # + = more upright
    status = grade(lost, -cfg["posture_gain_max"], cfg["posture_loss_max"],
                   -cfg["posture_gain_watch"], cfg["posture_loss_watch"])
    soft = status == "warn"
    if status == "ok":
        label = meaning = tip = ""
        word = "Posture kept"
    elif lost > 0:
        label = "Slightly standing up" if soft else "Standing up"
        meaning = "spine is a little more upright than at address" if soft else "spine stands up from its address bend"
        tip = "Keep your spine angle: turn around it instead of standing up out of it."
        word = label
    else:
        label = "Slightly bending over" if soft else "Bending over"
        meaning = "spine bends a little more than at address" if soft else "spine bends over more than at address"
        tip = "Keep your spine angle instead of dipping your chest toward the ball."
        word = label
    change = round(abs(lost))
    detail = "" if change == 0 else f" ({change}° {'more upright' if lost > 0 else 'more bent'})"
    row = Row("Spine bend kept", f"{deg_text(bend1)} ({deg_text(bend0)} at address)", word + detail, status,
              good=_either_way(cfg["posture_loss_max"], "more upright", cfg["posture_gain_max"], "more bent", "up to"),
              fix=_either_way(cfg["posture_loss_watch"], "more upright", cfg["posture_gain_watch"], "more bent",
                              "more than"))
    col = STATUS_COLORS[status]
    s = ctx.scale
    overlays = [
        Overlay("dashed", [tuple(hip1), tuple(hip1 + (sh0 - hip0))], REFERENCE_COLOR, "Address spine", show, 2),
        Overlay("segment", [tuple(hip1), tuple(sh1)], col, "", show, 2),
        Overlay("text", [tuple((hip1 + sh1) / 2 - forward * np.array([0.55 * s, 0.0]))], col,
                f"Spine {bend1:.0f} deg ({bend0:.0f} at address)", show),
    ]
    return BodyCheck(status, label, meaning, tip, row, overlays)


def trail_knee_kept(ctx: SwingContext, f: int, forward: float, show: tuple[int, int]) -> BodyCheck:
    """Trail (back) knee bend on frame f vs address; lost = the leg straightening.

    A watch item at most, never red: a trail leg that straightens early is a
    contributor (it makes losing posture easier) rather than a fault that costs
    shots by itself, and the 2D knee angle from behind is rough once the hips
    turn. Past knee_*_watch only the wording gets stronger."""
    cfg = ctx.cfg
    a = ctx.marks.address_frame
    hip, knee, ankle = (ctx.track(ctx.side(p, "trail")) for p in ("hip", "knee", "ankle"))
    if not all(np.all(np.isfinite(t[i])) for t in (hip, knee, ankle) for i in (a, f)):
        return BodyCheck("ok", "", "", "", Row("Back knee bend kept", "Not measured",
                         "Back leg not tracked on the address frame or this one", "error"), [])
    flex0 = 180.0 - angle_between_deg(hip[a] - knee[a], ankle[a] - knee[a])
    flex1 = 180.0 - angle_between_deg(hip[f] - knee[f], ankle[f] - knee[f])
    lost = flex0 - flex1  # + = straighter
    status = grade(lost, -cfg["knee_bend_max"], cfg["knee_straighten_max"],
                   -cfg["knee_bend_watch"], cfg["knee_straighten_watch"])
    soft = status == "warn"
    if status == "flag":
        status = Grade("warn", 1.0)  # capped: see the docstring
    if status == "ok":
        label = meaning = tip = ""
        word = "Bend kept"
    elif lost > 0:
        label = "Back knee slightly straightening" if soft else "Back knee straightening"
        meaning = ("back (trail) knee straightens a little" if soft else
                   "back (trail) knee straightens, nearly locking the leg")
        tip = "Keep the bend in your back knee as you start back: let your hips turn without locking the leg."
        word = "Slightly straightening" if soft else "Straightening"
    else:
        label = "Back knee slightly sinking" if soft else "Back knee sinking"
        meaning = "back (trail) knee bends a little more" if soft else "back (trail) knee bends more, sinking down"
        tip = "Keep your back knee bent as at address instead of squatting as you start back."
        word = "Slightly sinking" if soft else "Sinking"
    change = round(abs(lost))
    detail = "" if change == 0 else f" ({change}° {'straighter' if lost > 0 else 'more bent'})"
    row = Row("Back knee bend kept", f"{deg_text(flex1)} ({deg_text(flex0)} at address)", word + detail, status,
              good=_either_way(cfg["knee_straighten_max"], "straighter", cfg["knee_bend_max"], "more bent", "up to"),
              fix="none (a watch item only)")
    col = STATUS_COLORS[status]
    s = ctx.scale
    overlays = [
        Overlay("polyline", [tuple(hip[f]), tuple(knee[f]), tuple(ankle[f])], col, "", show, 2),
        Overlay("text", [(float(knee[f][0]) - forward * 0.55 * s, float(knee[f][1]))], col,
                f"Knee {flex1:.0f} deg ({flex0:.0f} at address)", show),
    ]
    return BodyCheck(status, label, meaning, tip, row, overlays)
