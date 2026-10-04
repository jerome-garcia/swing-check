"""The down-the-line checkpoints, in swing order.

Single source for the results page's checkpoint stepper. A checkpoint is
"built" once an analyzer with its name is registered; until then the app
shows it as coming soon. Keep this in step with the Roadmap in README.md.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Checkpoint:
    number: int
    title: str
    analyzer: str  # name the checkpoint's analyzer registers under
    phase: str | None  # swing phase whose frame it's judged on (None = not detected yet)
    description: str


DTL_CHECKPOINTS: tuple[Checkpoint, ...] = (
    Checkpoint(1, "Address", "address", "address",
               "Arms perpendicular to the ground, spine tilt, knee bend, back rounding."),
    Checkpoint(2, "Swing plane", "swing_plane", "address",
               "Your swing plane line: the shaft at address points at the belt buckle, at a sensible angle."),
    Checkpoint(3, "Takeaway", "takeaway", "takeaway",
               "When the club is parallel to the target line, the clubhead is still on the swing plane line from step 2."),
    Checkpoint(4, "Halfway back", "halfway_back", None,
               "Lead arm parallel to the ground: the shaft points at or just inside the ball (on plane)."),
    Checkpoint(5, "Top", "top", "top",
               "The lead arm matches the shoulders, 90° to the spine, and the hands are in the plane zone (between the swing plane line and the shoulder plane)."),
    Checkpoint(6, "Downswing", "downswing", "early_downswing",
               "Shaft parallel coming down: the clubhead is back on the swing plane line, flatter than at the takeaway (shallowing)."),
    Checkpoint(7, "Impact", "impact", "impact",
               "The hips stay back on the tush line (no early extension) and the spine bend is kept."),
    Checkpoint(8, "Follow-through", "follow_through", None,
               "Trail arm parallel after impact: the shaft exits on plane, on the same line as at halfway back."),
)


def checkpoints_json(view: str, registered: set[str]) -> list[dict]:
    if view != "dtl":
        return []
    return [{**asdict(cp), "built": cp.analyzer in registered} for cp in DTL_CHECKPOINTS]
