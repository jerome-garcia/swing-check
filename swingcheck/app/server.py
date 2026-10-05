"""SwingCheck web app: a local FastAPI server plus a static single-page frontend."""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from swingcheck.analyzers import REGISTRY, discover
from swingcheck.app import hosted as hosting
from swingcheck.app.frames import FrameReader
from swingcheck.checkpoints import checkpoints_json
from swingcheck.app.jobs import JobManager
from swingcheck.app.store import Store, SwingNotFound
from swingcheck.config import PROJECT_ROOT, load_config
from swingcheck.ingest import IngestError, VideoInfo, probe
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


class ClaimIn(BaseModel):
    key: str


class AnalyzeIn(BaseModel):
    phases: dict[str, int] = {}  # manual phase frames, e.g. {"impact": 412}; saved for later runs
    reset_phases: bool = False   # drop saved manual phases and use detection


def create_app(runs_dir: Path | None = None, hosted: bool = False) -> FastAPI:
    """The app. `hosted` runs it for the public (see swingcheck/app/hosted.py): every
    visitor sees only their own swings, with limits; otherwise it's single-user."""
    store = Store(runs_dir or PROJECT_ROOT / "runs")
    jobs = JobManager()
    frames = FrameReader()
    config = load_config()
    limits = config["hosted"] if hosted else None
    app = FastAPI(title="SwingCheck", docs_url=None, redoc_url=None)
    app.state.store = store
    app.state.jobs = jobs
    app.state.config = config
    if limits:
        hosting.start_sweeper(store, jobs, limits["keep_days"],
                              before_delete=lambda swing_id: frames.forget(store.root / swing_id / "normalized.mp4"))

    # --- owners (hosted only) ------------------------------------------------
    def owner(request: Request) -> str | None:
        """The visitor's owner hash when hosted; None runs single-user."""
        return hosting.owner_of(request.state.owner_key) if limits else None

    def owned(request: Request) -> list[dict[str, Any]]:
        return [with_expiry(s) for s in store.list(owner=owner(request))]

    def with_expiry(summary: dict[str, Any]) -> dict[str, Any]:
        if limits:
            end = hosting.expires_at(summary["created"], limits["keep_days"])
            summary["expires"] = end.isoformat(timespec="seconds") if end else None
        return summary

    def swing_or_404(swing_id: str, request: Request) -> Path:
        """The swing's folder, if it exists and (hosted) belongs to this visitor. Someone
        else's swing is "not found", so nobody can tell whether it exists."""
        try:
            folder = store.path(swing_id)
            if limits and store.meta(swing_id).owner != owner(request):
                raise SwingNotFound(swing_id)
            return folder
        except SwingNotFound:
            raise HTTPException(404, "Swing not found") from None

    def full_message() -> str:
        n = limits["max_swings"]
        return (f"You can keep {n} swing{'s' if n != 1 else ''} at a time. "
                "Delete one from Your swings to add a new one.")

    def check_not_busy() -> None:
        if limits and jobs.pending() >= limits["max_queued_jobs"]:
            raise HTTPException(503, "SwingCheck is busy with other swings right now. Try again in a few minutes.")

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
            "hosted": {k: limits[k] for k in ("max_swings", "keep_days", "max_upload_mb", "max_clip_seconds")}
            if limits else None,
        }

    @app.get("/api/owner")
    def get_owner(request: Request) -> dict[str, Any]:
        """Hosted: the visitor's key (for their private link) and how many swings they keep."""
        if not limits:
            raise HTTPException(404, "Not available")
        return {"key": request.state.owner_key, "swings": len(owned(request)), "max_swings": limits["max_swings"]}

    @app.post("/api/owner/claim")
    def claim_owner(body: ClaimIn, request: Request) -> dict[str, Any]:
        """Hosted: open a private link, so this browser sees that owner's swings."""
        if not limits:
            raise HTTPException(404, "Not available")
        if not hosting.valid_key(body.key):
            raise HTTPException(400, "That private link isn't valid. Copy the whole link and try again.")
        request.state.owner_key = body.key
        request.state.set_owner_cookie = True
        return {"swings": len(owned(request))}

    @app.post("/api/swings")
    def upload_swing(request: Request, file: UploadFile = File(...), view: str = Form(...),
                     agreed_terms: str | None = Form(None)) -> dict[str, Any]:
        check_view(view)
        if limits and not agreed_terms:
            raise HTTPException(400, "Agree to the Terms of use and Privacy notice to upload.")
        ext = Path(file.filename or "").suffix.lower()
        if ext not in VIDEO_EXTENSIONS:
            raise HTTPException(400, f"That doesn't look like a video ({ext or 'no extension'}). Use .mov or .mp4.")
        if limits and len(owned(request)) >= limits["max_swings"]:
            raise HTTPException(409, full_message())
        check_not_busy()
        meta = store.create(file.filename or "swing", view, owner=owner(request))
        meta.source_file = f"source{ext}"
        if limits:  # which terms this upload was agreed under, and when
            meta.notes["agreed_terms"] = {"version": agreed_terms[:40], "at": meta.created}
        with open(store.path(meta.id) / meta.source_file, "wb") as out:
            shutil.copyfileobj(file.file, out, length=1024 * 1024)
        store.save_meta(meta)
        if limits:
            too_long = clip_too_long(store.path(meta.id) / meta.source_file)
            if too_long:
                store.delete(meta.id)
                raise HTTPException(400, too_long)
        job = start_convert(meta.id)
        return {"id": meta.id, "job": job.to_json()}

    def clip_too_long(path: Path) -> str | None:
        """Hosted: refuse long clips (conversion and pose cost grow with length). A clip
        ffprobe can't read is left for the conversion to report."""
        try:
            seconds = float((probe(path).get("format") or {}).get("duration") or 0)
        except (IngestError, ValueError, OSError):
            return None
        limit = limits["max_clip_seconds"]
        if seconds > limit:
            return (f"That clip is {seconds:.0f} seconds long; the limit is {limit:g}. "
                    "Trim it to just the swing on your phone, then upload it again.")
        return None

    @app.get("/api/swings/{swing_id}/frames/{index}.jpg")
    def frame_image(swing_id: str, index: int, request: Request, w: int | None = None) -> Response:
        folder = swing_or_404(swing_id, request)
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
    def save_swing_marks(swing_id: str, body: MarksIn, request: Request) -> dict[str, Any]:
        folder = swing_or_404(swing_id, request)
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
    def set_view(swing_id: str, body: ViewIn, request: Request) -> dict[str, Any]:
        swing_or_404(swing_id, request)
        check_view(body.view)
        if jobs.active_for(swing_id):
            raise HTTPException(409, "This swing is still being processed.")
        meta = store.meta(swing_id)
        meta.view = body.view
        store.save_meta(meta)  # marks made for the other view no longer count
        return with_expiry(store.summary(swing_id))

    @app.post("/api/swings/{swing_id}/trim")
    def trim_swing(swing_id: str, body: TrimIn, request: Request) -> dict[str, Any]:
        folder = swing_or_404(swing_id, request)
        meta = store.meta(swing_id)
        if jobs.active_for(swing_id):
            raise HTTPException(409, "This swing is still being processed.")
        if not meta.source_file or not (folder / meta.source_file).exists():
            raise HTTPException(409, "The original video for this swing isn't available to re-trim.")
        if body.start is not None and body.end is not None and body.end <= body.start:
            raise HTTPException(400, "The end must be after the start.")
        check_not_busy()
        meta.trim_start, meta.trim_end = body.start, body.end
        store.save_meta(meta)
        frames.forget(folder / "normalized.mp4")
        job = start_convert(swing_id, body.start, body.end)
        return {"job": job.to_json()}

    @app.post("/api/swings/{swing_id}/analyze")
    def analyze_swing(swing_id: str, body: AnalyzeIn, request: Request) -> dict[str, Any]:
        folder = swing_or_404(swing_id, request)
        meta = store.meta(swing_id)
        if jobs.active_for(swing_id):
            raise HTTPException(409, "This swing is already being processed.")
        if store.status(swing_id) not in ("marked", "analyzed"):
            raise HTTPException(409, "Mark the ball (and club, for down-the-line) first.")
        if meta.view == "fo" and not FACE_ON_ENABLED:
            raise HTTPException(409, f"{FACE_ON_DISABLED_MESSAGE} Switch this swing to down-the-line to analyze it.")
        overrides = {k: v for k, v in body.phases.items() if k in ("address", "top", "impact")}
        check_not_busy()

        def run(progress):
            analyze(folder, meta.view, config, overrides=overrides, clear_overrides=body.reset_phases,
                    progress=progress)

        job = jobs.submit(swing_id, "analyze", run)
        return {"job": job.to_json()}

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str, request: Request) -> dict[str, Any]:
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(404, "Job not found")
        if limits:  # only the swing's owner may follow its job
            try:
                swing_or_404(job.swing_id, request)
            except HTTPException:
                raise HTTPException(404, "Job not found") from None
        return job.to_json()

    @app.get("/api/swings")
    def list_swings(request: Request) -> list[dict[str, Any]]:
        return owned(request)

    @app.get("/api/swings/{swing_id}")
    def get_swing(swing_id: str, request: Request) -> dict[str, Any]:
        folder = swing_or_404(swing_id, request)
        detail: dict[str, Any] = with_expiry(store.summary(swing_id))
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
    def summary_download(swing_id: str, request: Request) -> Response:
        folder = swing_or_404(swing_id, request)
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
    def delete_swing(swing_id: str, request: Request) -> dict[str, str]:
        swing_or_404(swing_id, request)
        if jobs.active_for(swing_id):
            raise HTTPException(409, "This swing is still being processed; wait for it to finish.")
        frames.forget(store.path(swing_id) / "normalized.mp4")  # Windows can't delete open files
        store.delete(swing_id)
        return {"deleted": swing_id}

    @app.get("/files/{swing_id}/{name}")
    def swing_file(swing_id: str, name: str, request: Request) -> FileResponse:
        swing_or_404(swing_id, request)
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

    if limits:
        @app.middleware("http")
        async def owner_cookie(request: Request, call_next):
            # Every visitor gets an owner key on their first request; swings belong to it.
            key = request.cookies.get(hosting.OWNER_COOKIE)
            fresh = not hosting.valid_key(key)
            request.state.owner_key = hosting.new_key() if fresh else key
            early = upload_refusal(request)
            response = early or await call_next(request)
            if fresh or getattr(request.state, "set_owner_cookie", False):
                response.set_cookie(hosting.OWNER_COOKIE, request.state.owner_key, max_age=hosting.COOKIE_MAX_AGE,
                                    httponly=True, samesite="lax", secure=request.url.scheme == "https")
            response.headers["X-Robots-Tag"] = "noindex, nofollow"
            return response

        def upload_refusal(request: Request) -> Response | None:
            """Refuse an upload before its body arrives: too big, too many swings, or busy."""
            if request.method != "POST" or request.url.path != "/api/swings":
                return None
            try:
                size = int(request.headers.get("content-length", ""))
            except ValueError:
                return JSONResponse({"detail": "Upload the video from the app's New swing page."}, 411)
            if size > limits["max_upload_mb"] * 1024 * 1024:
                return JSONResponse({"detail": f"That video is over {limits['max_upload_mb']} MB. Trim it to just "
                                     "the swing on your phone, then upload it again."}, 413)
            if len(owned(request)) >= limits["max_swings"]:
                return JSONResponse({"detail": full_message()}, 409)
            if jobs.pending() >= limits["max_queued_jobs"]:
                return JSONResponse({"detail": "SwingCheck is busy with other swings right now. "
                                     "Try again in a few minutes."}, 503)
            return None

    app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")
    return app
