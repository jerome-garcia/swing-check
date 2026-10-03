"""swing-check web app: a local FastAPI server plus a static single-page frontend."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from swingcheck.app.store import Store, SwingNotFound
from swingcheck.config import PROJECT_ROOT, load_config

STATIC = Path(__file__).parent / "static"


def create_app(runs_dir: Path | None = None) -> FastAPI:
    store = Store(runs_dir or PROJECT_ROOT / "runs")
    app = FastAPI(title="swing-check", docs_url=None, redoc_url=None)
    app.state.store = store
    app.state.config = load_config()

    def swing_or_404(swing_id: str):
        try:
            return store.path(swing_id)
        except SwingNotFound:
            raise HTTPException(404, "Swing not found") from None

    @app.get("/api/swings")
    def list_swings() -> list[dict[str, Any]]:
        return store.list()

    @app.get("/api/swings/{swing_id}")
    def get_swing(swing_id: str) -> dict[str, Any]:
        folder = swing_or_404(swing_id)
        detail: dict[str, Any] = store.summary(swing_id)
        for key, name in (("video", "video.json"), ("marks", "marks.json"), ("analysis", "analysis.json"),
                          ("phases", "phases.json")):
            path = folder / name
            detail[key] = json.loads(path.read_text()) if path.exists() else None
        detail["files"] = sorted(p.name for p in folder.iterdir()
                                 if p.suffix in (".mp4", ".png", ".txt") and p.name != "pose_debug.mp4")
        return detail

    @app.delete("/api/swings/{swing_id}")
    def delete_swing(swing_id: str) -> dict[str, str]:
        swing_or_404(swing_id)
        store.delete(swing_id)
        return {"deleted": swing_id}

    @app.get("/files/{swing_id}/{name}")
    def swing_file(swing_id: str, name: str) -> FileResponse:
        try:
            path = store.file(swing_id, name)
        except SwingNotFound:
            raise HTTPException(404, "File not found") from None
        # No caching: files are regenerated when a swing is re-analyzed.
        return FileResponse(path, headers={"Cache-Control": "no-store"})

    app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")
    return app
