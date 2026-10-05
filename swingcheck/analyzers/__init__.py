"""Analyzer registry.

An analyzer is a function decorated with `@register(...)` in any module in
this package. It receives a SwingContext and returns a Verdict. The pipeline
runs every registered analyzer whose view matches the clip, so adding a new
check is just adding a new module here; nothing else changes.

    from swingcheck.analyzers import SwingContext, Verdict, register

    @register("my_check", view="fo", title="My check")
    def my_check(ctx: SwingContext) -> Verdict:
        cfg = ctx.cfg                      # this analyzer's [analyzers.my_check] config
        hip = ctx.at(ctx.midpoint("left_hip", "right_hip"), "impact")
        ...
        return Verdict(status="ok", label="fine", summary="...", measurements={...})

`name`, `view` and `title` on the returned Verdict are filled in by the registry.
"""

from __future__ import annotations

import importlib
import pkgutil
import traceback
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from swingcheck import body
from swingcheck.geometry import target_sign, to_body_units
from swingcheck.models import Marks, PoseSeq
from swingcheck.phases import Phases

STATUSES = ("ok", "warn", "flag", "error")

Color = tuple[int, int, int]  # BGR

# Shared palette so the annotated video reads consistently across analyzers.
STATUS_COLORS: dict[str, Color] = {"ok": (80, 200, 80), "warn": (0, 200, 255), "flag": (60, 60, 230), "error": (160, 160, 160)}
# The drawing language, the same on every checkpoint:
#   green / yellow / red  anything measured, colored by its result (line, tick, mark, label)
#   white                 targets and address references: where it should be / where it was
#   magenta + grey        the swing plane line and its on-plane boundaries
#   cyan                  an earlier checkpoint's position (e.g. the clubhead at the takeaway)
# Shapes: clubhead = solid circle, hands = solid square, ball and other spots
# (a heel, where a shaft line lands) = hollow ring.
REFERENCE_COLOR: Color = (255, 255, 255)
PLANE_COLOR: Color = (255, 0, 255)       # magenta
PLANE_BAND_COLOR: Color = (150, 150, 150)
PAST_COLOR: Color = (255, 255, 0)        # cyan
BALL_COLOR: Color = REFERENCE_COLOR


class Grade(str):
    """A status ("ok" / "warn" / "flag") that also knows how deep into its band the value
    is (`depth`): 0 in the green, 0-1 across the yellow band, 1 + how far past the red
    limit (in widths of the yellow band on that side) in the red. A Row built with one
    picks the depth up, so the "Work on first" pick (swingcheck/priority.py) can
    compare faults across checkpoints."""

    depth: float

    def __new__(cls, status: str, depth: float = 0.0) -> Grade:
        g = super().__new__(cls, status)
        g.depth = depth
        return g

    def __reduce__(self):  # copies (e.g. dataclasses.asdict) keep the depth
        return Grade, (str(self), self.depth)


def cm_text(cm: float) -> str:
    """A rough distance for people, in whole centimetres (halves round up): '12 cm',
    or 'under 1 cm'. Magnitude only."""
    cm = abs(float(cm))
    if cm < 0.5:
        return "under 1 cm"
    return f"{int(cm + 0.5)} cm"


def deg_text(deg: float) -> str:
    """Whole degrees: '34°'."""
    return f"{round(float(deg)):.0f}°"


def clubhead_mark(xy, color: Color, show: tuple[int, int] | None, label: str = "") -> Overlay:
    """The clubhead: a solid circle."""
    return Overlay("circle", [(float(xy[0]), float(xy[1]))], color, label, show, 2)


def hands_mark(xy, color: Color, show: tuple[int, int] | None, label: str = "") -> Overlay:
    """The hands: a solid square."""
    return Overlay("square", [(float(xy[0]), float(xy[1]))], color, label, show, 2)


def spot_mark(xy, color: Color, show: tuple[int, int] | None, label: str = "") -> Overlay:
    """The ball, a heel, where a shaft line lands: a hollow ring."""
    return Overlay("ring", [(float(xy[0]), float(xy[1]))], color, label, show, 2)


# The "Fix" range line for a measurement that is never Fix (see watch_at_most).
WATCH_ONLY = "none (a watch item only)"


def watch_at_most(g: Grade) -> Grade:
    """For a measurement that's a style point more than a fault (it varies with the club,
    the camera, or good players' own styles): past its red limit it's still only "warn"
    (Watch), never "flag" (Fix). The wording can still say "too"."""
    return Grade("warn", min(1.0, g.depth)) if g == "flag" else g


def grade(value: float, ok_lo: float, ok_hi: float, watch_lo: float, watch_hi: float) -> Grade:
    """Green / yellow / red: "ok" inside [ok_lo, ok_hi], "warn" inside [watch_lo, watch_hi], else "flag"
    (a Grade, so it also carries how deep into the band the value is)."""
    if ok_lo <= value <= ok_hi:
        return Grade("ok", 0.0)
    high = value > ok_hi
    edge, limit = (ok_hi, watch_hi) if high else (ok_lo, watch_lo)
    width = abs(limit - edge)
    if not np.isfinite(width) or width <= 0:
        width = 1.0  # no usable yellow band on this side: count raw distance
    past_green = abs(value - edge)
    if watch_lo <= value <= watch_hi:
        return Grade("warn", min(1.0, past_green / width))
    return Grade("flag", 1.0 + abs(value - limit) / width if np.isfinite(limit) else 1.0 + past_green / width)


def pct(body_units: float) -> str:
    """A distance in torso lengths as a percent of torso length, e.g. 0.21 -> '21%'."""
    return f"{body_units * 100:.0f}%"


@dataclass
class Overlay:
    """Something an analyzer wants drawn on the annotated video.

    kind: "line" (infinite line through points[0] along points[1]-points[0]),
          "ray" (from points[0] through points[1], to the frame edge),
          "segment", "dashed" (a dashed segment, e.g. a target position; label at
          its end), "polyline" (through all points), "point",
          "vline" (vertical line at points[0].x: full height, or from
          points[0].y to points[1].y when two points are given),
          "text" (label at points[0]),
          "path" (one point per video frame; drawn as the hand-path trail up
          to the current frame, replacing the default wrist trail).
    frames: (first, last) frame range to draw on; None = whole video.
    """

    kind: str
    points: list[tuple[float, float]]
    color: Color = (255, 255, 255)
    label: str = ""
    frames: tuple[int, int] | None = None
    thickness: int = 2


@dataclass
class Row:
    """One line on the results card: a measurement, its value and what it means."""

    label: str  # e.g. "Knee bend"
    value: str  # formatted, e.g. "34°"
    note: str = ""  # short verdict in plain words, sentence case, no period, e.g. "Good bend"
    status: str = "ok"  # one of STATUSES; colors the row's dot
    good: str = ""  # the green range, e.g. "15–35°"
    fix: str = ""  # the red range, e.g. "under 10° or over 40°" (in between is yellow, Watch)
    depth: float | None = None  # how deep into its band (see Grade); taken from a Grade status

    def __post_init__(self) -> None:
        if self.depth is None and isinstance(self.status, Grade):
            self.depth = round(float(self.status.depth), 3)
        self.status = str(self.status)


@dataclass
class Verdict:
    status: str  # one of STATUSES
    label: str  # short result, e.g. "behind", "on plane"
    summary: str  # one sentence for the report
    measurements: dict[str, Any] = field(default_factory=dict)
    overlays: list[Overlay] = field(default_factory=list)
    rows: list[Row] = field(default_factory=list)  # compact display; falls back to measurements if empty
    tip: str = ""  # one-line "how to fix" for a yellow or red result
    name: str = ""
    view: str = ""
    title: str = ""
    phase: str | None = None  # swing phase the check is judged on (its key frame)
    frame: int | None = None  # key frame when it isn't a detected phase, e.g. a frame you marked

    def to_json(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("overlays")
        return d


@dataclass
class SwingContext:
    view: str
    pose: PoseSeq
    marks: Marks
    phases: Phases
    scale: float  # body length in px at address (see [scale])
    config: dict[str, Any]
    cfg: dict[str, Any] = field(default_factory=dict)  # current analyzer's own config section
    video_path: Path | None = None  # normalized video, for analyzers that need pixels
    _cache: dict[str, np.ndarray] = field(default_factory=dict, repr=False)

    def image(self, frame: int) -> np.ndarray:
        """The BGR video frame at `frame`."""
        if self.video_path is None:
            raise MissingData("No video available to this check")
        cap = cv2.VideoCapture(str(self.video_path))
        try:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame)
            ok, img = cap.read()
        finally:
            cap.release()
        if not ok:
            raise MissingData(f"Couldn't read video frame {frame}")
        return img

    def value(self, track: np.ndarray, frame: int, what: str) -> np.ndarray:
        """track[frame], raising MissingData (with `what` in the message) if it wasn't tracked."""
        v = track[frame]
        if not np.all(np.isfinite(v)):
            raise MissingData(f"Your {what} wasn't tracked on frame {frame}")
        return v

    @property
    def fps(self) -> float:
        return self.pose.fps

    @property
    def handedness(self) -> str:
        return self.config["golfer"]["handedness"]

    def side(self, part: str, which: str) -> str:
        """Landmark name for the lead/trail body part, e.g. side("shoulder", "trail") -> "right_shoulder"."""
        if which not in ("lead", "trail"):
            raise ValueError("which must be 'lead' or 'trail'")
        lead_is_left = self.handedness == "right"
        left = (which == "lead") == lead_is_left
        return f"{'left' if left else 'right'}_{part}"

    @property
    def target_sign(self) -> int:
        """+1 if the target is screen-right in this face-on clip, -1 if screen-left."""
        return target_sign(self.view, self.handedness, self.config["golfer"]["target_direction_fo"])

    def track(self, name: str) -> np.ndarray:
        """Cleaned (frames, 2) track for one landmark."""
        if name not in self._cache:
            self._cache[name] = body.cleaned(self.pose, name, self.config)
        return self._cache[name]

    def midpoint(self, a: str, b: str) -> np.ndarray:
        return (self.track(a) + self.track(b)) / 2

    def hands(self) -> np.ndarray:
        if "__hands" not in self._cache:
            self._cache["__hands"] = body.hands(self.pose, self.config)
        return self._cache["__hands"]

    def frame(self, phase: str) -> int:
        return getattr(self.phases, phase)

    def at(self, track: np.ndarray, phase: str) -> np.ndarray:
        """Value of a track at a phase; raises if it's missing there."""
        value = track[self.frame(phase)]
        if not np.all(np.isfinite(value)):
            raise MissingData(f"Your body wasn't tracked at {phase.replace('_', ' ')} (frame {self.frame(phase)})")
        return value

    def units(self, px: float) -> float:
        return to_body_units(px, self.scale)

    def cm(self, body_units: float) -> float:
        """Rough centimetres for a distance in torso lengths ([golfer] torso_cm)."""
        return body_units * self.config["golfer"]["torso_cm"]

    def distance_text(self, body_units: float) -> str:
        """'10 cm' for a distance in torso lengths (magnitude only; see cm_text)."""
        return cm_text(self.cm(body_units))

    def vspan(self, xy, half_height: float = 0.3) -> list[tuple[float, float]]:
        """Points for a short "vline" overlay centered on xy, +/- half_height body lengths."""
        x, y = float(xy[0]), float(xy[1])
        d = half_height * self.scale
        return [(x, y - d), (x, y + d)]


class MissingData(RuntimeError):
    """Raised by an analyzer when keypoints it needs weren't tracked."""


@dataclass
class Analyzer:
    name: str
    view: str
    title: str
    func: Callable[[SwingContext], Verdict]
    phase: str | None = None


REGISTRY: dict[str, Analyzer] = {}


def register(name: str, view: str, title: str, phase: str | None = None
             ) -> Callable[[Callable[[SwingContext], Verdict]], Callable[[SwingContext], Verdict]]:
    """Register an analyzer. `phase` is the swing phase it's judged on; the app shows
    that frame, drawn with only this analyzer's overlays, as its key frame."""
    if view not in ("dtl", "fo"):
        raise ValueError(f"view must be dtl or fo, not {view!r}")

    def decorator(func: Callable[[SwingContext], Verdict]) -> Callable[[SwingContext], Verdict]:
        if name in REGISTRY and REGISTRY[name].func is not func:
            raise ValueError(f"analyzer {name!r} registered twice")
        REGISTRY[name] = Analyzer(name=name, view=view, title=title, func=func, phase=phase)
        return func

    return decorator


def discover() -> None:
    """Import every module in this package so their @register calls run."""
    for module in pkgutil.iter_modules(__path__):
        importlib.import_module(f"{__name__}.{module.name}")


def analyzers_for(view: str, config: dict[str, Any]) -> list[Analyzer]:
    discover()
    disabled = set(config["analyzers"].get("disabled", []))
    return [a for a in REGISTRY.values() if a.view == view and a.name not in disabled]


def run_analyzers(ctx: SwingContext) -> list[Verdict]:
    """Run every analyzer matching the clip's view. One failing analyzer doesn't stop the rest."""
    verdicts = []
    for analyzer in analyzers_for(ctx.view, ctx.config):
        ctx.cfg = ctx.config["analyzers"].get(analyzer.name, {})
        try:
            verdict = analyzer.func(ctx)
        except MissingData as e:
            msg = str(e)
            msg = msg[:1].upper() + msg[1:]
            verdict = Verdict(status="error", label="Not measured", summary=msg if msg.endswith(".") else msg + ".")
        except Exception as e:  # noqa: BLE001 - report and keep going
            verdict = Verdict(
                status="error", label="Couldn't be checked", summary=f"Something went wrong measuring this: {e!r}",
                measurements={"traceback": traceback.format_exc()},
            )
        if verdict.status not in STATUSES:
            raise ValueError(f"{analyzer.name} returned unknown status {verdict.status!r}")
        verdict.name, verdict.view, verdict.title = analyzer.name, analyzer.view, analyzer.title
        verdict.phase = analyzer.phase
        verdicts.append(verdict)
    return verdicts
