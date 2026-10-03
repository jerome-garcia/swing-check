"""swing-check web app: a local FastAPI server plus a static single-page frontend."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from swingcheck.app.jobs import JobManager
from swingcheck.app.store import Store, SwingNotFound
from swingcheck.config import PROJECT_ROOT, load_config
from swingcheck.pipeline import ingest

STATIC = Path(__file__).parent / "static"
VIDEO_EXTENSIONS = {".mov", ".mp4", ".m4v", ".avi", ".mkv", ".webm", ".3gp"}


def create_app(runs_dir: Path | None = None) -> FastAPI:
    store = Store(runs_dir or PROJECT_ROOT / "runs")
    jobs = JobManager()
    config = load_config()
    app = FastAPI(title="swing-check", docs_url=None, redoc_url=None)
    app.state.store = store
    app.state.jobs = jobs
    app.state.config = config

    def start_convert(swing_id: str, start: float | None = None, end: float | None = None):
        folder = store.path(swing_id)
        meta = store.meta(swing_id)
        source = folder / meta.source_file

        def run(progress):
            ingest(source, folder, config, start=start, end=end, progress=progress)

        return jobs.submit(swing_id, "convert", run)

    @app.post("/api/swings")
    def upload_swing(file: UploadFile = File(...), view: str = Form(...)) -> dict[str, Any]:
        if view not in ("dtl", "fo"):
            raise HTTPException(400, "Choose down-the-line or face-on")
        ext = Path(file.filename or "").suffix.lower()
        if ext not in VIDEO_EXTENSIONS:
            raise HTTPException(400, f"That doesn't look like a video ({ext or 'no extension'}). Use .mov or .mp4.")
        meta = store.create(file.filename or "swing", view)
        meta.source_file = f"source{ext}"
        with open(store.path(meta.id) / meta.source_file, "wb") as out:
            shutil.copyfileobj(file.file, out, length=1024 * 1024)
        store.save_meta(meta)
        job = start_convert(meta.id)
        return {"id": meta.id, "job": job.to_json()}

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str) -> dict[str, Any]:
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(404, "Job not found")
        return job.to_json()

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
        job = jobs.active_for(swing_id) or jobs.latest_for(swing_id)
        detail["job"] = job.to_json() if job else None
        return detail

    @app.delete("/api/swings/{swing_id}")
    def delete_swing(swing_id: str) -> dict[str, str]:
        swing_or_404(swing_id)
        if jobs.active_for(swing_id):
            raise HTTPException(409, "This swing is still being processed; wait for it to finish.")
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
