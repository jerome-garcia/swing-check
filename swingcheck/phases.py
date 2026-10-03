"""Swing phase detection from the hand path: address, takeaway, top, early downswing, impact.

Image y grows downward, so "higher hands" means smaller y. All speed
thresholds are relative to the clip's own peak hand speed and all distances
are in body units, so the same settings work for any camera distance and for
slowed-down playback.

Steps:
  1. Downswing peak D: the frame where the hands move down fastest.
  2. Impact: the bottom of the hand path after D (middle of the frames within
     a small tolerance of the lowest point).
  3. Top: the highest hand point between D and the last time (before D) the
     hands were down at impact height.
  4. Address: the last still stretch of hands at or before that low point.
  5. Takeaway / early downswing: where the hands cross a set fraction of the
     address-to-top height on the way up and on the way down.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from swingcheck.pose import clean_track

PHASE_NAMES = ("address", "takeaway", "top", "early_downswing", "impact")
KEY_PHASES = ("address", "top", "impact")  # the ones a user can override


class PhaseError(RuntimeError):
    pass


@dataclass
class Phases:
    address: int
    takeaway: int
    top: int
    early_downswing: int
    impact: int
    # Which key phases came from a manual override rather than detection.
    manual: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, int]:
        return {name: getattr(self, name) for name in PHASE_NAMES}


def _first(mask: np.ndarray) -> int | None:
    hits = np.flatnonzero(mask)
    return int(hits[0]) if hits.size else None


def _last(mask: np.ndarray) -> int | None:
    hits = np.flatnonzero(mask)
    return int(hits[-1]) if hits.size else None


def checkpoints(y: np.ndarray, address: int, top: int, impact: int,
                takeaway_fraction: float, downswing_fraction: float) -> tuple[int, int]:
    """Takeaway and early-downswing frames: where the hands cross the given fraction of
    the address->top height, on the way up and on the way down."""
    rise = y[address] - y[top]
    with np.errstate(invalid="ignore"):
        up = _first(y[address + 1 : top + 1] <= y[address] - takeaway_fraction * rise)
        down = _first(y[top : impact + 1] >= y[address] - downswing_fraction * rise)
    takeaway = address + 1 + up if up is not None else (address + top) // 2
    early = top + down if down is not None else (top + impact) // 2
    return takeaway, early


def detect_phases(hands: np.ndarray, fps: float, scale: float, cfg: dict[str, Any],
                  search: tuple[int, int] | None = None) -> Phases:
    """Detect phases from a (frames, 2) hand track in pixels; `scale` is body length in pixels.

    `search` limits where the downswing is looked for (e.g. the part of the
    clip tracked at full frame rate, away from seams with other passes).
    """
    n = len(hands)
    xy = clean_track(hands, fps, max_gap_ms=0, smoothing_ms=cfg["smoothing_ms"])
    y = xy[:, 1]
    if np.isfinite(y).sum() < 10:
        raise PhaseError("Hands were not tracked in enough frames to find the swing.")

    vy = np.gradient(y)  # px/frame, positive = moving down
    speed = np.linalg.norm(np.gradient(xy, axis=0), axis=1)

    # 1. Fastest downward hand movement = middle of the downswing.
    vy_search = vy
    if search is not None:
        lo, hi = max(0, search[0]), min(n - 1, search[1])
        windowed = np.full(n, np.nan)
        windowed[lo : hi + 1] = vy[lo : hi + 1]
        if np.isfinite(windowed).any():
            vy_search = windowed
    d = int(np.nanargmax(vy_search))

    # 2. Impact: hands bottom out after D (first frame they stop dropping).
    stop = _first(vy[d + 1 :] <= 0)
    end = d + 1 + stop if stop is not None else n - 1
    lowest = d + int(np.nanargmax(y[d : end + 1]))
    # Hands linger near the bottom for a few frames; which one is lowest is
    # mostly noise, so take the middle of that near-flat stretch.
    floor = y[lowest] - cfg["impact_plateau_tolerance"] * scale
    lo, hi = lowest, lowest
    while lo - 1 >= d and y[lo - 1] >= floor:
        lo -= 1
    while hi + 1 <= end and y[hi + 1] >= floor:
        hi += 1
    impact = (lo + hi) // 2
    # Hands bottom out slightly before contact for many players; a fixed shift
    # (tuned on your own clips) can correct a consistent bias.
    impact = min(n - 1, max(d, impact + int(round(cfg["impact_offset_ms"] * fps / 1000))))

    # 3. Top: highest hands between "last time hands were low before D" and D.
    low_level = y[impact] - cfg["low_level_tolerance"] * scale
    with np.errstate(invalid="ignore"):
        is_low = y >= low_level
    t = d
    while t > 0 and (is_low[t] or not np.isfinite(y[t])):  # skip back out of the low zone near D
        t -= 1
    before = _last(is_low[:t])
    low_start = before if before is not None else 0
    top = low_start + int(np.nanargmin(y[low_start : d + 1]))
    if top >= impact:
        raise PhaseError("Could not separate top of backswing from impact.")

    # 4. Address: last still stretch at or before the low point preceding the backswing.
    peak = float(np.nanpercentile(speed, 98))
    still = speed < cfg["still_speed_fraction"] * peak
    run = max(1, int(round(cfg["still_min_ms"] * fps / 1000)))
    address = None
    for i in range(min(low_start, top - 1), run - 2, -1):
        if still[max(0, i - run + 1) : i + 1].all():
            address = i
            break
    if address is not None:
        rest = np.nanmedian(xy[max(0, address - run + 1) : address + 1], axis=0)
    else:
        # Hands never fully still (slow drift, forward press): rest at their
        # lowest point before the backswing.
        address = int(np.nanargmax(y[: low_start + 1]))
        rest = xy[address]
    # Step forward until the hands have actually left their resting spot.
    tol = cfg["address_move_tolerance"] * scale
    while address + 1 < top and np.linalg.norm(xy[address + 1] - rest) <= tol:
        address += 1

    # 5. Checkpoints.
    takeaway, early = checkpoints(y, address, top, impact, cfg["takeaway_fraction"], cfg["downswing_fraction"])
    phases = Phases(address=address, takeaway=takeaway, top=top, early_downswing=early, impact=impact)
    validate(phases, n)
    return phases


def validate(phases: Phases, frame_count: int) -> None:
    values = [getattr(phases, name) for name in PHASE_NAMES]
    if not all(0 <= v < frame_count for v in values):
        raise PhaseError(f"Phase frame out of range: {phases.as_dict()}")
    if not all(a <= b for a, b in zip(values, values[1:])):
        raise PhaseError(f"Phases out of order: {phases.as_dict()}")


def apply_overrides(
    auto: Phases | None, overrides: dict[str, int], hands: np.ndarray, fps: float, cfg: dict[str, Any], frame_count: int
) -> Phases:
    """Replace detected key phases with manual ones and recompute the checkpoints between them."""
    if auto is None and not all(k in overrides for k in KEY_PHASES):
        missing = [k for k in KEY_PHASES if k not in overrides]
        raise PhaseError(f"Automatic detection failed; set the rest manually: --{' --'.join(missing)}")
    key = {k: overrides.get(k, getattr(auto, k) if auto else None) for k in KEY_PHASES}
    if not overrides:
        assert auto is not None
        return auto
    y = clean_track(hands, fps, max_gap_ms=0, smoothing_ms=cfg["smoothing_ms"])[:, 1]
    takeaway, early = checkpoints(y, key["address"], key["top"], key["impact"],
                                  cfg["takeaway_fraction"], cfg["downswing_fraction"])
    phases = Phases(
        address=key["address"], takeaway=takeaway, top=key["top"], early_downswing=early,
        impact=key["impact"], manual=[k for k in KEY_PHASES if k in overrides],
    )
    validate(phases, frame_count)
    return phases


def load_overrides(path: Path, signature: dict[str, Any]) -> dict[str, int]:
    """Saved manual phase frames, if made on the same normalized video."""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}
    if data.get("video_signature") != signature:
        return {}
    return {k: int(v) for k, v in data.get("overrides", {}).items() if k in KEY_PHASES}


def save_phases(path: Path, phases: Phases, auto: Phases | None, overrides: dict[str, int], signature: dict[str, Any]) -> None:
    payload = {
        "phases": phases.as_dict(),
        "manual": phases.manual,
        "auto": auto.as_dict() if auto else None,
        "overrides": overrides,
        "video_signature": signature,
    }
    path.write_text(json.dumps(payload, indent=2))


def get_phases(
    run_dir: Path,
    hands: np.ndarray,
    fps: float,
    scale: float,
    config: dict[str, Any],
    signature: dict[str, Any],
    new_overrides: dict[str, int],
    clear_overrides: bool = False,
    marked_address: int | None = None,
    search: tuple[int, int] | None = None,
    marked_takeaway: int | None = None,
) -> tuple[Phases, str | None]:
    """Detect phases, merge saved + new manual overrides, save phases.json.

    `marked_address` (the frame the user marked on) is used as address unless
    an explicit address override exists; it isn't saved as an override.
    `marked_takeaway` (the frame the user marked the takeaway on) replaces the
    detected takeaway checkpoint when it falls between address and top.
    Returns (phases, detection_error) where detection_error explains a failed
    automatic detection that overrides papered over.
    """
    path = run_dir / "phases.json"
    cfg = config["phases"]
    overrides = {} if clear_overrides else load_overrides(path, signature)
    overrides.update(new_overrides)
    try:
        auto: Phases | None = detect_phases(hands, fps, scale, cfg, search)
        error = None
    except PhaseError as e:
        auto, error = None, str(e)
    effective = dict(overrides)
    if marked_address is not None and "address" not in effective:
        effective["address"] = marked_address
    phases = apply_overrides(auto, effective, hands, fps, cfg, len(hands))
    if marked_takeaway is not None and phases.address < marked_takeaway <= phases.top:
        phases.takeaway = marked_takeaway
        phases.manual = [*phases.manual, "takeaway"]
    save_phases(path, phases, auto, overrides, signature)
    return phases, error
