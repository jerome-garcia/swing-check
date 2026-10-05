"""SwingCheck web app: a local FastAPI server plus a static single-page frontend."""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import os
import shutil
import subprocess
import time
from importlib import metadata
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from swingcheck.analyzers import REGISTRY, discover
from swingcheck.app import admin
from swingcheck.app import hosted as hosting
from swingcheck.app.frames import FrameReader
from swingcheck.checkpoints import checkpoints_json
from swingcheck.app.jobs import JobManager
from swingcheck.app.store import Store, SwingNotFound
from swingcheck.config import PROJECT_ROOT, load_config
from swingcheck.ingest import IngestError, VideoInfo, probe
from swingcheck.output.summary_pdf import summary_pdf
from swingcheck.pipeline import (PipelineError, analyze, ingest, load_camera_check, load_suggested, save_marks,
                                 suggest_frames)

log = logging.getLogger(__name__)
STATIC = Path(__file__).parent / "static"
VIDEO_EXTENSIONS = {".mov", ".mp4", ".m4v", ".avi", ".mkv", ".webm", ".3gp"}

# Face-on is held back for a future release: its checks haven't been validated on
# real clips yet. Existing face-on swings can still be opened. Flip this to enable it.
FACE_ON_ENABLED = False
FACE_ON_DISABLED_MESSAGE = "Face-on analysis is coming in a future release."


def app_version() -> str:
    """The running version for the footer: the release tag when a tag is checked out (as on the
    server, e.g. "v0.1.0-alpha"), "<tag>-<commits since>-g<hash>" in development, else the
    package version."""
    try:
        out = subprocess.run(["git", "-C", str(PROJECT_ROOT), "describe", "--tags", "--always"],
                             capture_output=True, text=True, timeout=5)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        return "v" + metadata.version("swingcheck")
    except metadata.PackageNotFoundError:
        return "unknown"


class CheckpointMarksIn(BaseModel):
    frame: int
    points: dict[str, tuple[float, float]] = {}


class MarksIn(BaseModel):
    address_frame: int
    points: dict[str, tuple[float, float]]
    checkpoints: dict[str, CheckpointMarksIn] = {}  # optional, e.g. {"takeaway": {...}}


class ViewIn(BaseModel):
    view: str


class HandednessIn(BaseModel):
    handedness: str


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
    events = admin.EventLog(store.root / admin.EVENTS_FILE)
    daily_codes = admin.DailyCode()
    started_at = time.time()

    def job_finished(job) -> None:
        """Log each finished job for the admin page: kind, outcome, wait, and run time, plus
        the camera check's findings after a conversion. Nothing about who or which swing."""
        fields: dict[str, Any] = {
            "ok": job.state == "done",
            "wait_s": round(job.started - job.created, 1) if job.started else None,
            "run_s": round(job.finished - job.started, 1) if job.started and job.finished else None,
        }
        if job.error:  # with the swing's folder (and so its id) blanked out
            error = job.error.replace(str(store.root / job.swing_id), "<swing>").replace(job.swing_id, "<swing>")
            fields["error"] = error[:500]
        if job.kind == "convert" and job.state == "done":
            try:
                suggest = json.loads((store.root / job.swing_id / "suggest.json").read_text())
                fields["camera"] = [f["title"] for f in suggest.get("camera") or []]
            except (OSError, ValueError):
                pass
        events.add(job.kind, **fields)

    jobs = JobManager(on_finish=job_finished)
    frames = FrameReader()
    config = load_config()
    limits = config["hosted"] if hosted else None
    version = app_version()  # once: a release is a restart
    app = FastAPI(title="SwingCheck", docs_url=None, redoc_url=None)
    app.state.store = store
    app.state.jobs = jobs
    app.state.config = config
    uploads = hosting.UploadCounter()
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

    def client_ip(request: Request) -> str:
        return request.client.host if request.client else "unknown"

    def check_not_busy() -> None:
        if limits and jobs.pending() >= limits["max_queued_jobs"]:
            raise HTTPException(503, "SwingCheck is busy with other swings right now. Try again in a few minutes.")

    def swing_config(meta) -> dict[str, Any]:
        """The config for one swing: the app's, with this golfer's handedness."""
        cfg = copy.deepcopy(config)
        cfg["golfer"]["handedness"] = meta.handedness
        return cfg

    def start_convert(swing_id: str, start: float | None = None, end: float | None = None):
        folder = store.path(swing_id)
        meta = store.meta(swing_id)
        source = folder / meta.source_file
        cfg = swing_config(meta)

        def run(progress):
            info = ingest(source, folder, cfg, start=start, end=end, progress=progress)
            # Starting frames for the marking screen. They're only a convenience: a clip where
            # the swing can't be found (or any other failure here) still converts.
            try:
                suggest_frames(folder, info, cfg, progress=progress)
            except Exception:  # noqa: BLE001
                log.exception("Couldn't suggest frames for %s", swing_id)

        return jobs.submit(swing_id, "convert", run)

    def check_handedness(handedness: str) -> None:
        if handedness not in ("right", "left"):
            raise HTTPException(400, "Choose right-handed or left-handed")

    def check_view(view: str) -> None:
        if view not in ("dtl", "fo"):
            raise HTTPException(400, "Choose down-the-line or face-on")
        if view == "fo" and not FACE_ON_ENABLED:
            raise HTTPException(400, FACE_ON_DISABLED_MESSAGE)

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        """For the deploy script: up, how many jobs are queued or running, and how many
        uploads are arriving. It waits for both to be 0 before restarting, since a restart
        loses running jobs and cuts uploads off."""
        return {"ok": True, "jobs": jobs.pending(), "uploads": uploading, "version": version}

    @app.get("/api/features")
    def features() -> dict[str, Any]:
        discover()
        built = {name for name, a in REGISTRY.items() if a.view == "dtl"}
        return {
            "version": version,
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
                     handedness: str = Form("right"), agreed_terms: str | None = Form(None)) -> dict[str, Any]:
        check_view(view)
        check_handedness(handedness)
        if limits and not agreed_terms:
            raise HTTPException(400, "Agree to the Terms of use and Privacy notice to upload.")
        ext = Path(file.filename or "").suffix.lower()
        if ext not in VIDEO_EXTENSIONS:
            raise HTTPException(400, f"That doesn't look like a video ({ext or 'no extension'}). Use .mov or .mp4.")
        if limits and len(owned(request)) >= limits["max_swings"]:
            raise HTTPException(409, full_message())
        check_not_busy()
        meta = store.create(file.filename or "swing", view, owner=owner(request), handedness=handedness)
        meta.source_file = f"source{ext}"
        if limits:  # which terms this upload was agreed under, and when
            meta.notes["agreed_terms"] = {"version": agreed_terms[:40], "at": meta.created}
            uploads.record(client_ip(request))
        with open(store.path(meta.id) / meta.source_file, "wb") as out:
            shutil.copyfileobj(file.file, out, length=1024 * 1024)
        store.save_meta(meta)
        if limits:
            too_long = clip_too_long(store.path(meta.id) / meta.source_file)
            if too_long:
                store.delete(meta.id)
                raise HTTPException(400, too_long)
        job = start_convert(meta.id)
        who = owner(request)  # hosted: a code that matches this browser today only (admin.DailyCode)
        took = round(time.monotonic() - getattr(request.state, "upload_started", time.monotonic()), 1)
        events.add("upload", view=view, handedness=handedness, upload_s=took,
                   **({"u": daily_codes.code(who)} if who else {}))
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

    def conversion_token(folder: Path) -> str | None:
        """Changes whenever the video is converted again (e.g. trimmed): frame URLs carry it."""
        video = folder / "normalized.mp4"
        return str(video.stat().st_mtime_ns) if video.exists() else None

    @app.get("/api/swings/{swing_id}/frames/{index}.jpg")
    def frame_image(swing_id: str, index: int, request: Request, w: int | None = None,
                    c: str | None = None) -> Response:
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
        # A frame never changes within one conversion, so with this conversion's token (?c=)
        # the browser may keep it: going back to a frame is then instant. "private" keeps
        # Cloudflare from caching it (frames belong to one visitor).
        cache = "private, max-age=86400, immutable" if c and c == conversion_token(folder) else "no-store"
        return Response(data, media_type="image/jpeg", headers={"Cache-Control": cache})

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

    @app.post("/api/swings/{swing_id}/handedness")
    def set_handedness(swing_id: str, body: HandednessIn, request: Request) -> dict[str, Any]:
        """Right- or left-handed. Marks stay (they're points on the video); the analysis
        is redone, since lead and trail swap."""
        swing_or_404(swing_id, request)
        check_handedness(body.handedness)
        if jobs.active_for(swing_id):
            raise HTTPException(409, "This swing is still being processed.")
        meta = store.meta(swing_id)
        meta.handedness = body.handedness
        store.save_meta(meta)
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

        cfg = swing_config(meta)

        def run(progress):
            analyze(folder, meta.view, cfg, overrides=overrides, clear_overrides=body.reset_phases,
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
        info = VideoInfo.load(folder / "video.json") if (folder / "video.json").exists() else None
        if detail["video"]:
            detail["video"]["version"] = conversion_token(folder)
        detail["suggested"] = load_suggested(folder, info) if info else None
        detail["camera_check"] = load_camera_check(folder, info, detail["handedness"]) if info else None
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

    # Uploads whose video is still arriving or being saved: the deploy script waits for
    # these too (a restart mid-upload makes the visitor upload again). The middleware runs
    # on the event loop's one thread, so a plain counter is enough.
    uploading = 0

    @app.middleware("http")
    async def count_uploads(request, call_next):
        nonlocal uploading
        if request.method != "POST" or request.url.path != "/api/swings":
            return await call_next(request)
        uploading += 1
        request.state.upload_started = time.monotonic()  # the upload event logs how long sending took
        try:
            return await call_next(request)
        finally:
            uploading -= 1

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
            if uploads.count(client_ip(request)) >= limits["max_uploads_per_ip_per_day"]:
                return JSONResponse({"detail": "That's the most uploads from your network for today. "
                                     "Try again tomorrow."}, 429)
            if jobs.pending() >= limits["max_queued_jobs"]:
                return JSONResponse({"detail": "SwingCheck is busy with other swings right now. "
                                     "Try again in a few minutes."}, 503)
            return None

    page = index_page()

    # Admin page (swingcheck/app/admin.py): numbers only. Hosted, Cloudflare Access guards
    # /admin with an email one-time code; the app also checks the email Access vouches for
    # against SWINGCHECK_ADMIN_EMAIL (set on the server, not in the repo). Without it, or
    # from anyone else, /admin doesn't exist.
    admin_email = os.environ.get("SWINGCHECK_ADMIN_EMAIL", "").strip().lower()

    def admin_allowed(request: Request) -> bool:
        if not hosted:
            return True  # your own computer
        who = request.headers.get("cf-access-authenticated-user-email", "").strip().lower()
        return bool(admin_email) and bool(request.headers.get("cf-access-jwt-assertion")) and who == admin_email

    @app.get("/admin", include_in_schema=False)
    def admin_page(request: Request) -> HTMLResponse:
        if not admin_allowed(request):
            raise HTTPException(404, "Not Found")
        live = admin.live_status(jobs.snapshot(), uploading, store.root, version, started_at)
        return HTMLResponse(admin.page(admin.summary(events.read(), live)),
                            headers={"Cache-Control": "no-store"})

    # The app's pages (clean addresses, routed in the browser: static/app.js). Opening or
    # reloading any of them gets the app, which then shows that page.
    @app.get("/", include_in_schema=False)
    @app.get("/index.html", include_in_schema=False)
    @app.get("/new", include_in_schema=False)
    @app.get("/terms", include_in_schema=False)
    @app.get("/privacy", include_in_schema=False)
    @app.get("/swing/{swing_id}", include_in_schema=False)
    @app.get("/swing/{swing_id}/mark", include_in_schema=False)
    def index(swing_id: str | None = None) -> HTMLResponse:
        return HTMLResponse(page)

    app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")
    return app


def index_page() -> str:
    """index.html with its CSS and JS addressed by a fingerprint of their contents
    (style.css?v=…), so after a release every browser fetches the new files instead of
    mixing cached old ones with the new page. An import map does the same for the
    modules app.js imports (./util.js and the rest), which a ?v= on app.js alone wouldn't."""
    assets = sorted(STATIC.glob("*.js")) + sorted(STATIC.glob("*.css"))
    digest = hashlib.sha256(b"".join(p.name.encode() + p.read_bytes() for p in assets)).hexdigest()[:12]
    imports = {f"/{p.name}": f"/{p.name}?v={digest}" for p in assets if p.suffix == ".js"}
    import_map = f'<script type="importmap">{json.dumps({"imports": imports})}</script>\n  '
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    for old, new in (('href="/style.css"', f'href="/style.css?v={digest}"'),
                     ('<script type="module" src="/app.js">', f'{import_map}<script type="module" src="/app.js?v={digest}">')):
        if old not in html:
            raise RuntimeError(f"index.html no longer contains {old!r}: update index_page()")
        html = html.replace(old, new)
    return html
