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
               "The shaft line at address points at the belt buckle, at a sensible angle."),
    Checkpoint(3, "Takeaway", "takeaway", "takeaway",
               "When the club is parallel to the target line, the clubhead is still on the address shaft line."),
    Checkpoint(4, "Halfway back", "halfway_back", None,
               "Lead arm parallel to the ground: the hands split the trail biceps and the shaft points just inside the ball."),
    Checkpoint(5, "Top", "top", "top",
               "The lead arm matches the shoulders, 90° to the spine, and the hands are on plane."),
    Checkpoint(6, "Downswing", "downswing", "early_downswing",
               "Shaft parallel coming down: the club is back on plane, flatter than at the takeaway (shallowing)."),
    Checkpoint(7, "Impact", "impact", "impact", "Details to be defined."),
    Checkpoint(8, "Follow-through", "follow_through", None,
               "The club exits on the same line as the backswing."),
)


def checkpoints_json(view: str, registered: set[str]) -> list[dict]:
    if view != "dtl":
        return []
    return [{**asdict(cp), "built": cp.analyzer in registered} for cp in DTL_CHECKPOINTS]
