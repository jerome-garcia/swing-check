"""Swings on disk: one folder per swing under runs/, plus a small swing.json with app metadata.

Folders made before the app existed (no swing.json) are still listed; their
details are inferred from the files the pipeline wrote.
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from swingcheck.ingest import VideoInfo
from swingcheck.pipeline import load_marks

META = "swing.json"
SETTINGS = "settings.json"  # app-wide choices, in the runs folder itself (e.g. the marking reference)
ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,120}$")

# Status, in order: uploaded -> converted -> marked -> analyzed.
STATUSES = ("uploaded", "converted", "marked", "analyzed")


@dataclass
class SwingMeta:
    id: str
    name: str
    created: str  # ISO timestamp
    view: str | None = None
    source_file: str | None = None  # original upload, inside the swing folder
    trim_start: float | None = None
    trim_end: float | None = None
    notes: dict[str, Any] = field(default_factory=dict)


class SwingNotFound(KeyError):
    pass


class Store:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    # --- ids and paths -------------------------------------------------------
    def path(self, swing_id: str) -> Path:
        if not ID_PATTERN.match(swing_id) or swing_id in (".", ".."):
            raise SwingNotFound(swing_id)
        p = self.root / swing_id
        if not p.is_dir():
            raise SwingNotFound(swing_id)
        return p

    def new_id(self, filename: str) -> str:
        stem = re.sub(r"[^A-Za-z0-9]+", "-", Path(filename).stem).strip("-").lower()[:40] or "swing"
        base = f"{datetime.now():%Y%m%d-%H%M%S}-{stem}"
        candidate, n = base, 2
        while (self.root / candidate).exists():
            candidate, n = f"{base}-{n}", n + 1
        return candidate

    # --- metadata ------------------------------------------------------------
    def create(self, filename: str, view: str) -> SwingMeta:
        swing_id = self.new_id(filename)
        (self.root / swing_id).mkdir()
        meta = SwingMeta(id=swing_id, name=Path(filename).stem, created=datetime.now().isoformat(timespec="seconds"),
                         view=view)
        self.save_meta(meta)
        return meta

    def save_meta(self, meta: SwingMeta) -> None:
        (self.root / meta.id / META).write_text(json.dumps(asdict(meta), indent=2))

    def meta(self, swing_id: str) -> SwingMeta:
        folder = self.path(swing_id)
        meta_path = folder / META
        if meta_path.exists():
            try:
                return SwingMeta(**json.loads(meta_path.read_text()))
            except (TypeError, ValueError):
                pass
        return self._inferred_meta(folder)

    def _inferred_meta(self, folder: Path) -> SwingMeta:
        view = None
        for name in ("analysis.json", "marks.json"):
            data = _read_json(folder / name)
            if data and data.get("view") in ("dtl", "fo"):
                view = data["view"]
                break
        video = _read_json(folder / "video.json") or {}
        created = datetime.fromtimestamp(folder.stat().st_mtime).isoformat(timespec="seconds")
        return SwingMeta(id=folder.name, name=folder.name.replace("_", " "), created=created, view=view,
                         trim_start=video.get("trim_start"), trim_end=video.get("trim_end"))

    # --- status --------------------------------------------------------------
    def status(self, swing_id: str) -> str:
        folder = self.path(swing_id)
        if not ((folder / "video.json").exists() and (folder / "normalized.mp4").exists()):
            return "uploaded"
        meta = self.meta(swing_id)
        info = VideoInfo.load(folder / "video.json")
        # Marks only count if they were made on this exact conversion (same trim).
        if meta.view is None or load_marks(folder / "marks.json", meta.view, info) is None:
            return "converted"
        analysis = _read_json(folder / "analysis.json")
        if (analysis and analysis.get("view") == meta.view
                and (folder / "analysis.json").stat().st_mtime >= (folder / "marks.json").stat().st_mtime):
            return "analyzed"
        return "marked"

    # --- listing ------------------------------------------------------------
    def list(self) -> list[dict[str, Any]]:
        items = []
        for folder in self.root.iterdir():
            if not folder.is_dir() or not ID_PATTERN.match(folder.name):
                continue
            try:
                items.append(self.summary(folder.name))
            except SwingNotFound:
                continue
        items.sort(key=lambda s: s["created"], reverse=True)
        return items

    def summary(self, swing_id: str) -> dict[str, Any]:
        folder = self.path(swing_id)
        meta = self.meta(swing_id)
        status = self.status(swing_id)
        verdicts = []
        if status == "analyzed":
            analysis = _read_json(folder / "analysis.json") or {}
            verdicts = [{"name": v.get("name"), "title": v.get("title"), "status": v.get("status"), "label": v.get("label")}
                        for v in analysis.get("verdicts", [])]
        thumb = next((n for n in ("address.png", "top.png") if (folder / n).exists()), None)
        return {**asdict(meta), "status": status, "verdicts": verdicts, "thumbnail": thumb}

    def delete(self, swing_id: str) -> None:
        shutil.rmtree(self.path(swing_id))
        if self.reference_id() == swing_id:
            self.set_reference(None)

    # --- marking reference ---------------------------------------------------
    # One swing the user likes (say a pro's clip), shown beside each marking step.
    def reference_id(self) -> str | None:
        ref = (_read_json(self.root / SETTINGS) or {}).get("reference")
        try:
            return ref if ref and self.path(ref) else None
        except SwingNotFound:
            return None

    def set_reference(self, swing_id: str | None) -> None:
        settings = _read_json(self.root / SETTINGS) or {}
        settings["reference"] = swing_id
        (self.root / SETTINGS).write_text(json.dumps(settings, indent=2))

    # --- files ---------------------------------------------------------------
    def file(self, swing_id: str, name: str) -> Path:
        """A file inside a swing folder; refuses anything that would escape it."""
        folder = self.path(swing_id).resolve()
        target = (folder / name).resolve()
        if folder not in target.parents or not target.is_file():
            raise SwingNotFound(f"{swing_id}/{name}")
        return target


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None
