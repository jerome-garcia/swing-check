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
from typing import Any

import numpy as np

from swingcheck import body
from swingcheck.geometry import target_sign, to_body_units
from swingcheck.models import Marks, PoseSeq
from swingcheck.phases import Phases

STATUSES = ("ok", "warn", "flag", "error")

Color = tuple[int, int, int]  # BGR

# Shared palette so the annotated video reads consistently across analyzers.
STATUS_COLORS: dict[str, Color] = {"ok": (80, 200, 80), "warn": (0, 200, 255), "flag": (60, 60, 230), "error": (160, 160, 160)}
REFERENCE_COLOR: Color = (255, 255, 255)  # address-position reference lines
BALL_COLOR: Color = (255, 255, 0)


@dataclass
class Overlay:
    """Something an analyzer wants drawn on the annotated video.

    kind: "line" (infinite line through points[0] along points[1]-points[0]),
          "ray" (from points[0] through points[1], to the frame edge),
          "segment", "point",
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
class Verdict:
    status: str  # one of STATUSES
    label: str  # short result, e.g. "behind", "on plane"
    summary: str  # one sentence for the report
    measurements: dict[str, Any] = field(default_factory=dict)
    overlays: list[Overlay] = field(default_factory=list)
    name: str = ""
    view: str = ""
    title: str = ""

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
    _cache: dict[str, np.ndarray] = field(default_factory=dict, repr=False)

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
            raise MissingData(f"not tracked at {phase} (frame {self.frame(phase)})")
        return value

    def units(self, px: float) -> float:
        return to_body_units(px, self.scale)

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


REGISTRY: dict[str, Analyzer] = {}


def register(name: str, view: str, title: str) -> Callable[[Callable[[SwingContext], Verdict]], Callable[[SwingContext], Verdict]]:
    if view not in ("dtl", "fo"):
        raise ValueError(f"view must be dtl or fo, not {view!r}")

    def decorator(func: Callable[[SwingContext], Verdict]) -> Callable[[SwingContext], Verdict]:
        if name in REGISTRY and REGISTRY[name].func is not func:
            raise ValueError(f"analyzer {name!r} registered twice")
        REGISTRY[name] = Analyzer(name=name, view=view, title=title, func=func)
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
            verdict = Verdict(status="error", label="no data", summary=f"Couldn't measure: {e}.")
        except Exception as e:  # noqa: BLE001 - report and keep going
            verdict = Verdict(
                status="error", label="crashed", summary=f"Analyzer failed: {e!r}",
                measurements={"traceback": traceback.format_exc()},
            )
        if verdict.status not in STATUSES:
            raise ValueError(f"{analyzer.name} returned unknown status {verdict.status!r}")
        verdict.name, verdict.view, verdict.title = analyzer.name, analyzer.view, analyzer.title
        verdicts.append(verdict)
    return verdicts
