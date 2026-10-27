"""The checkpoints for each camera view, in swing order.

Single source for the results page's checkpoint stepper. A checkpoint is
"built" once an analyzer with its name is registered; until then the app
shows it as coming soon. Keep this in step with docs/checkpoints.md.
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
               "Your setup: arms hanging straight down, spine tilted forward, knees softly bent, upper back straight."),
    Checkpoint(2, "Swing plane", "swing_plane", "address",
               "The club shaft at address points at your belt buckle, at a normal angle. This line is your swing plane for the later steps."),
    Checkpoint(3, "Takeaway", "takeaway", "takeaway",
               "Club parallel to the ground, pointing along the target line: the clubhead is still on your swing plane line, and your spine and back knee keep their address bend."),
    Checkpoint(4, "Halfway back", "halfway_back", None,
               "Front arm parallel to the ground: the shaft points at the ball, and your spine and back knee keep their address bend."),
    Checkpoint(5, "Top", "top", "top",
               "Your front arm lines up with your shoulders (about 90° to your spine), your hands sit above your back heel, and your spine keeps its bend."),
    Checkpoint(6, "Downswing", "downswing", "early_downswing",
               "Shaft parallel to the ground on the way down: the clubhead is back on your swing plane line, flatter than on the way back (shallowing), and your spine keeps its bend."),
    Checkpoint(7, "Impact", "impact", "impact",
               "Your hips stay back instead of pushing toward the ball (no early extension), and your spine keeps its bend."),
    Checkpoint(8, "Follow-through", "follow_through", None,
               "Back arm parallel to the ground after impact: the shaft points at the ball again, on the same line as halfway back."),
)


# Face-on: the camera square to the golfer's chest. It sees side-to-side movement (sway,
# weight shift, the head) and shaft lean, which down-the-line can't. Analyzer names are
# global, so these carry an fo_ prefix.
FO_CHECKPOINTS: tuple[Checkpoint, ...] = (
    Checkpoint(1, "Address", "fo_address", "address",
               "Your setup from the front: feet about shoulder width apart, the ball in the right place between them, and your spine tilted slightly away from the target."),
    Checkpoint(2, "Top", "fo_top", "top",
               "At the top, your hips stay inside your back foot (no sway) and your head stays about where it started."),
    Checkpoint(3, "Downswing", "fo_downswing", None,
               "Shaft parallel to the ground on the way down: your hips have moved toward the target, and your head stays back."),
    Checkpoint(4, "Impact", "fo_impact", "impact",
               "Your hands are ahead of the ball, your hips have moved toward the target, and your head is behind the ball."),
    Checkpoint(5, "Finish", "fo_finish", None,
               "Balanced at the finish: your hips and head over your front foot."),
)

CHECKPOINTS: dict[str, tuple[Checkpoint, ...]] = {"dtl": DTL_CHECKPOINTS, "fo": FO_CHECKPOINTS}


def checkpoints_json(view: str, registered: set[str]) -> list[dict]:
    return [{**asdict(cp), "built": cp.analyzer in registered} for cp in CHECKPOINTS.get(view, ())]
