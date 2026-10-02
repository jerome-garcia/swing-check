"""Shared data types passed between pipeline stages."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

Point = tuple[float, float]  # (x, y) in normalized-video pixel coordinates

# Points the user clicks on the address frame, in click order, per view.
REQUIRED_MARKS: dict[str, tuple[str, ...]] = {
    "dtl": ("ball", "clubhead", "grip"),
    "fo": ("ball",),
}


@dataclass
class Marks:
    view: str
    address_frame: int
    points: dict[str, Point]
    # Identifies the normalized video the marks were made on, so a re-trim or
    # re-encode invalidates them instead of silently misplacing points.
    video_signature: dict[str, float | int | None] = field(default_factory=dict)

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(asdict(self), indent=2))

    @classmethod
    def load(cls, path: Path) -> "Marks":
        data = json.loads(path.read_text())
        data["points"] = {k: (float(v[0]), float(v[1])) for k, v in data["points"].items()}
        return cls(**data)

    def is_complete(self) -> bool:
        return all(name in self.points for name in REQUIRED_MARKS[self.view])
