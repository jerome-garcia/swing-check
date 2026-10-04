"""swing-check web app: a local FastAPI server plus a static single-page frontend."""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from swingcheck.analyzers import REGISTRY, discover
from swingcheck.app.frames import FrameReader
from swingcheck.checkpoints import checkpoints_json
from swingcheck.app.jobs import JobManager
from swingcheck.app.store import Store, SwingNotFound
from swingcheck.config import PROJECT_ROOT, load_config
from swingcheck.ingest import VideoInfo
from swingcheck.output.summary_pdf import summary_pdf
from swingcheck.pipeline import PipelineError, analyze, ingest, load_suggested, save_marks, suggest_frames

log = logging.getLogger(__name__)
STATIC = Path(__file__).parent / "static"
VIDEO_EXTENSIONS = {".mov", ".mp4", ".m4v", ".avi", ".mkv", ".webm", ".3gp"}

# Face-on is held back for a future release: its checks haven't been validated on
# real clips yet. Existing face-on swings can still be opened. Flip this to enable it.
FACE_ON_ENABLED = False
FACE_ON_DISABLED_MESSAGE = "Face-on analysis is coming in a future release."


class CheckpointMarksIn(BaseModel):
    frame: int
    points: dict[str, tuple[float, float]] = {}


class MarksIn(BaseModel):
    address_frame: int
    points: dict[str, tuple[float, float]]
    checkpoints: dict[str, CheckpointMarksIn] = {}  # optional, e.g. {"takeaway": {...}}


class ViewIn(BaseModel):
    view: str


class TrimIn(BaseModel):
    start: float | None = None  # seconds into the original video
    end: float | None = None


class AnalyzeIn(BaseModel):
    phases: dict[str, int] = {}  # manual phase frames, e.g. {"impact": 412}; saved for later runs
    reset_phases: bool = False   # drop saved manual phases and use detection


def create_app(runs_dir: Path | None = None) -> FastAPI:
    store = Store(runs_dir or PROJECT_ROOT / "runs")
    jobs = JobManager()
    frames = FrameReader()
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
            info = ingest(source, folder, config, start=start, end=end, progress=progress)
            # Starting frames for the marking screen. They're only a convenience: a clip where
            # the swing can't be found (or any other failure here) still converts.
            try:
                suggest_frames(folder, info, config, progress=progress)
            except Exception:  # noqa: BLE001
                log.exception("Couldn't suggest frames for %s", swing_id)

        return jobs.submit(swing_id, "convert", run)

    def check_view(view: str) -> None:
        if view not in ("dtl", "fo"):
            raise HTTPException(400, "Choose down-the-line or face-on")
        if view == "fo" and not FACE_ON_ENABLED:
            raise HTTPException(400, FACE_ON_DISABLED_MESSAGE)

    @app.get("/api/features")
    def features() -> dict[str, Any]:
        discover()
        built = {name for name, a in REGISTRY.items() if a.view == "dtl"}
        return {
            "face_on": FACE_ON_ENABLED,
            "face_on_message": FACE_ON_DISABLED_MESSAGE,
            "checkpoints": {"dtl": checkpoints_json("dtl", built)},
        }

    @app.post("/api/swings")
    def upload_swing(file: UploadFile = File(...), view: str = Form(...)) -> dict[str, Any]:
        check_view(view)
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

    @app.get("/api/swings/{swing_id}/frames/{index}.jpg")
    def frame_image(swing_id: str, index: int, w: int | None = None) -> Response:
        folder = swing_or_404(swing_id)
        video = folder / "normalized.mp4"
        if not video.exists():
            raise HTTPException(404, "Video not converted yet")
        active = jobs.active_for(swing_id)
        if active and active.kind == "convert":  # don't hold the file open while it's being rewritten
            raise HTTPException(409, "The video is being converted")
        try:
            data = frames.jpeg(video, index, width=w if w and w >= 64 else None)
        except (IndexError, FileNotFoundError):
            raise HTTPException(404, "Frame not found") from None
        return Response(data, media_type="image/jpeg", headers={"Cache-Control": "no-store"})

    @app.post("/api/swings/{swing_id}/marks")
    def save_swing_marks(swing_id: str, body: MarksIn) -> dict[str, Any]:
        folder = swing_or_404(swing_id)
        meta = store.meta(swing_id)
        if jobs.active_for(swing_id):
            raise HTTPException(409, "This swing is still being processed.")
        if not (folder / "video.json").exists():
            raise HTTPException(409, "The video hasn't been converted yet.")
        info = VideoInfo.load(folder / "video.json")
        try:
            marks = save_marks(folder, meta.view, body.address_frame, body.points, info,
                               checkpoints={k: v.model_dump() for k, v in body.checkpoints.items()})
        except PipelineError as e:
            raise HTTPException(400, str(e)) from None
        return {"view": marks.view, "address_frame": marks.address_frame, "points": marks.points,
                "checkpoints": {k: {"frame": c.frame, "points": c.points} for k, c in marks.checkpoints.items()}}

    @app.post("/api/swings/{swing_id}/view")
    def set_view(swing_id: str, body: ViewIn) -> dict[str, Any]:
        swing_or_404(swing_id)
        check_view(body.view)
        if jobs.active_for(swing_id):
            raise HTTPException(409, "This swing is still being processed.")
        meta = store.meta(swing_id)
        meta.view = body.view
        store.save_meta(meta)  # marks made for the other view no longer count
        return store.summary(swing_id)

    @app.post("/api/swings/{swing_id}/trim")
    def trim_swing(swing_id: str, body: TrimIn) -> dict[str, Any]:
        folder = swing_or_404(swing_id)
        meta = store.meta(swing_id)
        if jobs.active_for(swing_id):
            raise HTTPException(409, "This swing is still being processed.")
        if not meta.source_file or not (folder / meta.source_file).exists():
            raise HTTPException(409, "The original video for this swing isn't available to re-trim.")
        if body.start is not None and body.end is not None and body.end <= body.start:
            raise HTTPException(400, "The end must be after the start.")
        meta.trim_start, meta.trim_end = body.start, body.end
        store.save_meta(meta)
        frames.forget(folder / "normalized.mp4")
        job = start_convert(swing_id, body.start, body.end)
        return {"job": job.to_json()}

    @app.post("/api/swings/{swing_id}/analyze")
    def analyze_swing(swing_id: str, body: AnalyzeIn) -> dict[str, Any]:
        folder = swing_or_404(swing_id)
        meta = store.meta(swing_id)
        if jobs.active_for(swing_id):
            raise HTTPException(409, "This swing is already being processed.")
        if store.status(swing_id) not in ("marked", "analyzed"):
            raise HTTPException(409, "Mark the ball (and club, for down-the-line) first.")
        if meta.view == "fo" and not FACE_ON_ENABLED:
            raise HTTPException(409, f"{FACE_ON_DISABLED_MESSAGE} Switch this swing to down-the-line to analyze it.")
        overrides = {k: v for k, v in body.phases.items() if k in ("address", "top", "impact")}

        def run(progress):
            analyze(folder, meta.view, config, overrides=overrides, clear_overrides=body.reset_phases,
                    progress=progress)

        job = jobs.submit(swing_id, "analyze", run)
        return {"job": job.to_json()}

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
        detail["suggested"] = (load_suggested(folder, VideoInfo.load(folder / "video.json"))
                               if (folder / "video.json").exists() else None)
        detail["files"] = sorted(p.name for p in folder.iterdir()
                                 if p.suffix in (".mp4", ".png", ".txt") and p.name != "pose_debug.mp4")
        job = jobs.active_for(swing_id) or jobs.latest_for(swing_id)
        detail["job"] = job.to_json() if job else None
        return detail

    @app.get("/api/swings/{swing_id}/summary.pdf")
    def summary_download(swing_id: str) -> Response:
        folder = swing_or_404(swing_id)
        analysis_path = folder / "analysis.json"
        if not analysis_path.exists():
            raise HTTPException(409, "Analyze this swing first, then download its summary.")
        meta = store.meta(swing_id)
        pdf = summary_pdf(folder, meta.name, meta.created or "", json.loads(analysis_path.read_text()),
                          config["golfer"]["torso_cm"])
        filename = "".join(c if c.isalnum() or c in "-_" else "-" for c in meta.name).strip("-") or "swing"
        return Response(pdf, media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="{filename}-summary.pdf"',
                                 "Cache-Control": "no-store"})

    @app.delete("/api/swings/{swing_id}")
    def delete_swing(swing_id: str) -> dict[str, str]:
        swing_or_404(swing_id)
        if jobs.active_for(swing_id):
            raise HTTPException(409, "This swing is still being processed; wait for it to finish.")
        frames.forget(store.path(swing_id) / "normalized.mp4")  # Windows can't delete open files
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

    @app.middleware("http")
    async def revalidate_static(request, call_next):
        # Always revalidate the app's own JS/CSS so an update is picked up on reload.
        response = await call_next(request)
        if not request.url.path.startswith(("/api/", "/files/")):
            response.headers["Cache-Control"] = "no-cache"
        return response

    app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")
    return app
