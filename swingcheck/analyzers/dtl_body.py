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

from swingcheck.analyzers import REFERENCE_COLOR, STATUS_COLORS, Overlay, Row, SwingContext, grade
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



def with_body(status: str, label: str, meaning: str, tip: str, body: list["BodyCheck"]) -> tuple[str, str, str, str]:
    """A check's result with its body rows folded in: the worst status, faults appended
    to the label and the summary sentence, and their tips added."""
    status = max([status] + [b.status for b in body], key=ORDER.__getitem__)
    faults = [b for b in body if b.label]
    if faults:
        label = ", ".join([label] + [b.label[0].lower() + b.label[1:] for b in faults])
        meaning = f"{meaning} Your {' and '.join(b.meaning for b in faults)}."
    tip = " ".join(t for t in [tip] + [b.tip for b in body] if t)
    return status, label, meaning, tip


def _limits(cfg: dict, lose_max: str, lose_watch: str, lose_word: str, gain_max: str, gain_watch: str,
            gain_word: str) -> str:
    return (f"green up to {cfg[lose_max]:g}° {lose_word} or {cfg[gain_max]:g}° {gain_word}, "
            f"red past {cfg[lose_watch]:g}° {lose_word} or {cfg[gain_watch]:g}° {gain_word}")


def posture_kept(ctx: SwingContext, f: int, forward: float, show: tuple[int, int]) -> BodyCheck:
    """Spine bend on frame f vs address; lost = standing up."""
    cfg = ctx.cfg
    a = ctx.marks.address_frame
    hip0, sh0 = ctx.midpoint("left_hip", "right_hip")[a], ctx.midpoint("left_shoulder", "right_shoulder")[a]
    hip1, sh1 = ctx.midpoint("left_hip", "right_hip")[f], ctx.midpoint("left_shoulder", "right_shoulder")[f]
    if not all(np.all(np.isfinite(p)) for p in (hip0, sh0, hip1, sh1)):
        return BodyCheck("ok", "", "", "", Row("Spine bend kept", "not measured",
                         "hips or shoulders not tracked on the address or this frame", "error"), [])
    bend0 = tilt_from_vertical_deg(sh0 - hip0, forward, up=True)
    bend1 = tilt_from_vertical_deg(sh1 - hip1, forward, up=True)
    lost = bend0 - bend1  # + = more upright
    status = grade(lost, -cfg["posture_gain_max"], cfg["posture_loss_max"],
                   -cfg["posture_gain_watch"], cfg["posture_loss_watch"])
    soft = status == "warn"
    if status == "ok":
        label = meaning = tip = ""
        word = "posture kept"
    elif lost > 0:
        label = "Slightly standing up" if soft else "Standing up"
        meaning = "spine is a little more upright than at address" if soft else "spine stands up from its address bend"
        tip = "Keep your spine angle as you start back: turn around it instead of lifting up."
        word = label.lower()
    else:
        label = "Slightly bending over" if soft else "Bending over"
        meaning = "spine bends a little more than at address" if soft else "spine bends over more than at address"
        tip = "Keep your spine angle as you start back instead of dipping your chest toward the ball."
        word = label.lower()
    limits = _limits(cfg, "posture_loss_max", "posture_loss_watch", "lost",
                     "posture_gain_max", "posture_gain_watch", "gained")
    row = Row("Spine bend kept", f"{bend1:.0f}° (address {bend0:.0f}°)",
              f"{abs(lost):.0f}° {'more upright' if lost >= 0 else 'more bent'} · {word} ({limits})", status)
    col = STATUS_COLORS[status]
    s = ctx.scale
    overlays = [
        Overlay("dashed", [tuple(hip1), tuple(hip1 + (sh0 - hip0))], REFERENCE_COLOR, "address spine", show, 2),
        Overlay("segment", [tuple(hip1), tuple(sh1)], col, "", show, 2),
        Overlay("text", [tuple((hip1 + sh1) / 2 - forward * np.array([0.55 * s, 0.0]))], col,
                f"spine {bend1:.0f} deg (address {bend0:.0f})", show),
    ]
    return BodyCheck(status, label, meaning, tip, row, overlays)


def trail_knee_kept(ctx: SwingContext, f: int, forward: float, show: tuple[int, int]) -> BodyCheck:
    """Trail knee flex on frame f vs address; lost = the leg straightening.

    A watch item at most, never red: a trail leg that straightens early is a
    contributor (it makes losing posture easier) rather than a fault that costs
    shots by itself, and the 2D knee angle from behind is rough once the hips
    turn. Past knee_*_watch only the wording gets stronger."""
    cfg = ctx.cfg
    a = ctx.marks.address_frame
    hip, knee, ankle = (ctx.track(ctx.side(p, "trail")) for p in ("hip", "knee", "ankle"))
    if not all(np.all(np.isfinite(t[i])) for t in (hip, knee, ankle) for i in (a, f)):
        return BodyCheck("ok", "", "", "", Row("Trail knee flex kept", "not measured",
                         "trail leg not tracked on the address or this frame", "error"), [])
    flex0 = 180.0 - angle_between_deg(hip[a] - knee[a], ankle[a] - knee[a])
    flex1 = 180.0 - angle_between_deg(hip[f] - knee[f], ankle[f] - knee[f])
    lost = flex0 - flex1  # + = straighter
    status = grade(lost, -cfg["knee_bend_max"], cfg["knee_straighten_max"],
                   -cfg["knee_bend_watch"], cfg["knee_straighten_watch"])
    soft = status == "warn"
    if status == "flag":
        status = "warn"  # capped: see the docstring
    if status == "ok":
        label = meaning = tip = ""
        word = "flex kept"
    elif lost > 0:
        label = "Trail knee slightly straightening" if soft else "Trail knee straightening"
        meaning = "trail knee straightens a little" if soft else "trail knee straightens, nearly locking the trail leg"
        tip = "Keep the flex in your trail knee as you start back; let the hips turn without locking the leg."
        word = "slightly straightening" if soft else "straightening"
    else:
        label = "Trail knee slightly sinking" if soft else "Trail knee sinking"
        meaning = "trail knee bends a little more" if soft else "trail knee bends more, sinking down"
        tip = "Keep your trail knee flex as at address instead of squatting as you start back."
        word = "slightly sinking" if soft else "sinking"
    limits = (f"green up to {cfg['knee_straighten_max']:g}° straighter or {cfg['knee_bend_max']:g}° more bent; "
              f"yellow beyond, never red")
    row = Row("Trail knee flex kept", f"{flex1:.0f}° (address {flex0:.0f}°)",
              f"{abs(lost):.0f}° {'straighter' if lost >= 0 else 'more bent'} · {word} ({limits})", status)
    col = STATUS_COLORS[status]
    s = ctx.scale
    overlays = [
        Overlay("polyline", [tuple(hip[f]), tuple(knee[f]), tuple(ankle[f])], col, "", show, 2),
        Overlay("text", [(float(knee[f][0]) - forward * 0.55 * s, float(knee[f][1]))], col,
                f"knee {flex1:.0f} deg (address {flex0:.0f})", show),
    ]
    return BodyCheck(status, label, meaning, tip, row, overlays)
