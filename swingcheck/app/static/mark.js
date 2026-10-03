import { api, el, pollJob, postJSON, progressBlock, swingUrl } from "./util.js";
import { swingHeader } from "./swing.js";

const POINTS = {
  dtl: ["ball", "clubhead", "grip"],
  fo: ["ball"],
};
// Label offsets (CSS px) keep the ball and clubhead labels apart; those points sit together.
const POINT_INFO = {
  ball: { label: "Ball", hint: "Center of the ball", color: "#ffffff", dx: 11, dy: 20 },
  clubhead: { label: "Clubhead", hint: "The hosel, where the shaft meets the head", color: "#ffc233", dx: -70, dy: -10 },
  grip: { label: "Grip", hint: "Center of your hands on the shaft", color: "#4fb3ff", dx: 11, dy: -9 },
};
const LOUPE_SIZE = 150;
const LOUPE_ZOOM = 4;

export async function renderMark(view, id, isCurrent) {
  const s = await api(`/api/swings/${encodeURIComponent(id)}`);
  if (!isCurrent()) return;
  if (!s.video || (s.job && ["queued", "running"].includes(s.job.state))) {
    location.replace(swingUrl(id));
    return;
  }

  const v = s.video;
  const required = POINTS[s.view];
  const marksValid = s.status === "marked" || s.status === "analyzed";
  const sameView = s.marks && s.marks.view === s.view;
  const state = {
    frame: marksValid && sameView ? Math.min(s.marks.address_frame, v.frame_count - 1) : 0,
    // Point positions survive a re-trim (the camera didn't move), so keep them as a starting point.
    points: sameView ? { ...s.marks.points } : {},
    cursor: null, // {x, y} in video pixels while hovering/aiming
    aiming: false,
    touch: false,
  };

  // --- Frame images ---------------------------------------------------------
  const canvas = el("canvas", { class: "mark-canvas", tabindex: "0", "aria-label": "Video frame: click to place the next point" });
  const ctx = canvas.getContext("2d");
  let preview = null; // scaled image for the current frame
  let full = null;    // full-resolution image, for the loupe
  let loadToken = 0;
  let fullTimer = null;

  function frameUrl(frame, width) {
    return `/api/swings/${encodeURIComponent(id)}/frames/${frame}.jpg${width ? `?w=${width}` : ""}`;
  }

  function loadImage(url) {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = () => reject(new Error("frame failed to load"));
      img.src = url;
    });
  }

  async function showFrame(frame) {
    const token = ++loadToken;
    clearTimeout(fullTimer);
    full = null;
    const width = Math.min(v.width, Math.round(canvas.width || 720));
    try {
      const img = await loadImage(frameUrl(frame, width));
      if (token !== loadToken) return;
      preview = img;
      draw();
      // Once scrubbing settles, fetch full resolution for precise aiming.
      fullTimer = setTimeout(async () => {
        const big = await loadImage(frameUrl(frame)).catch(() => null);
        if (token === loadToken && big) { full = big; draw(); }
      }, 250);
    } catch { /* a newer frame request superseded this one, or the server is busy */ }
  }

  // --- Layout ---------------------------------------------------------------
  function fitCanvas() {
    const stage = canvas.parentElement;
    if (!stage) return;
    const maxW = stage.clientWidth;
    // Leave room below the frame for the scrubber and its caption.
    const top = stage.getBoundingClientRect().top + window.scrollY;
    const maxH = Math.max(260, window.innerHeight - top - 90);
    const scale = Math.min(maxW / v.width, maxH / v.height);
    const cssW = Math.floor(v.width * scale);
    const cssH = Math.floor(v.height * scale);
    const dpr = window.devicePixelRatio || 1;
    canvas.style.width = `${cssW}px`;
    canvas.style.height = `${cssH}px`;
    canvas.width = Math.round(cssW * dpr);
    canvas.height = Math.round(cssH * dpr);
    draw();
  }

  const toCanvas = (x, y) => [x * canvas.width / v.width, y * canvas.height / v.height];

  function eventToVideo(e) {
    const rect = canvas.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width * v.width;
    const y = (e.clientY - rect.top) / rect.height * v.height;
    return { x: Math.max(0, Math.min(v.width - 1, x)), y: Math.max(0, Math.min(v.height - 1, y)) };
  }

  // --- Drawing --------------------------------------------------------------
  function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const img = full || preview;
    if (img) ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    const dpr = window.devicePixelRatio || 1;

    if (state.points.clubhead && state.points.grip) {
      const [ax, ay] = toCanvas(...state.points.clubhead);
      const [bx, by] = toCanvas(...state.points.grip);
      ctx.strokeStyle = POINT_INFO.clubhead.color;
      ctx.lineWidth = 2 * dpr;
      ctx.beginPath(); ctx.moveTo(ax, ay); ctx.lineTo(bx, by); ctx.stroke();
    }
    for (const name of required) {
      const p = state.points[name];
      if (!p) continue;
      const [cx, cy] = toCanvas(...p);
      ctx.lineWidth = 3 * dpr;
      ctx.strokeStyle = "rgba(0,0,0,0.8)";
      ctx.beginPath(); ctx.arc(cx, cy, 7 * dpr, 0, Math.PI * 2); ctx.stroke();
      ctx.lineWidth = 2 * dpr;
      ctx.strokeStyle = POINT_INFO[name].color;
      ctx.beginPath(); ctx.arc(cx, cy, 7 * dpr, 0, Math.PI * 2); ctx.stroke();
      const info = POINT_INFO[name];
      label(ctx, info.label, cx + info.dx * dpr, cy + info.dy * dpr, info.color, dpr);
    }
    if (state.cursor && nextPoint()) drawLoupe(dpr);
  }

  function drawLoupe(dpr) {
    const img = full || preview;
    if (!img) return;
    const size = LOUPE_SIZE * dpr;
    const [cx, cy] = toCanvas(state.cursor.x, state.cursor.y);
    // Above the finger on touch screens; to the upper right of the mouse otherwise.
    let lx = state.touch ? cx - size / 2 : cx + 24 * dpr;
    let ly = state.touch ? cy - size - 40 * dpr : cy - size - 24 * dpr;
    if (lx + size > canvas.width) lx = cx - size - 24 * dpr;
    lx = Math.max(0, Math.min(canvas.width - size, lx));
    if (ly < 0) ly = Math.min(canvas.height - size, cy + 40 * dpr);

    const srcSize = (LOUPE_SIZE / LOUPE_ZOOM) * (img.naturalWidth / v.width) * (v.width / (canvas.width / dpr));
    const sx = state.cursor.x * img.naturalWidth / v.width - srcSize / 2;
    const sy = state.cursor.y * img.naturalHeight / v.height - srcSize / 2;
    ctx.save();
    ctx.beginPath(); ctx.rect(lx, ly, size, size); ctx.clip();
    ctx.fillStyle = "#000"; ctx.fillRect(lx, ly, size, size);
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(img, sx, sy, srcSize, srcSize, lx, ly, size, size);
    ctx.restore();
    ctx.strokeStyle = "#fff"; ctx.lineWidth = 1 * dpr;
    ctx.strokeRect(lx, ly, size, size);
    ctx.strokeStyle = "rgba(255,230,0,0.9)";
    ctx.beginPath();
    ctx.moveTo(lx + size / 2, ly); ctx.lineTo(lx + size / 2, ly + size);
    ctx.moveTo(lx, ly + size / 2); ctx.lineTo(lx + size, ly + size / 2);
    ctx.stroke();
    // Crosshair at the actual aim point.
    ctx.strokeStyle = "rgba(255,230,0,0.9)";
    ctx.beginPath();
    ctx.moveTo(cx - 10 * dpr, cy); ctx.lineTo(cx + 10 * dpr, cy);
    ctx.moveTo(cx, cy - 10 * dpr); ctx.lineTo(cx, cy + 10 * dpr);
    ctx.stroke();
  }

  // --- Points ---------------------------------------------------------------
  const nextPoint = () => required.find(n => !state.points[n]) || null;

  function placePoint(p) {
    const name = nextPoint();
    if (!name) return;
    state.points[name] = [Math.round(p.x * 10) / 10, Math.round(p.y * 10) / 10];
    refresh();
  }

  function undo() {
    const placed = required.filter(n => state.points[n]);
    if (placed.length) delete state.points[placed[placed.length - 1]];
    refresh();
  }

  canvas.addEventListener("pointerdown", e => {
    state.touch = e.pointerType !== "mouse";
    state.aiming = true;
    state.cursor = eventToVideo(e);
    canvas.setPointerCapture(e.pointerId);
    draw();
  });
  canvas.addEventListener("pointermove", e => {
    if (e.pointerType !== "mouse" && !state.aiming) return;
    state.touch = e.pointerType !== "mouse";
    state.cursor = eventToVideo(e);
    draw();
  });
  canvas.addEventListener("pointerup", e => {
    if (!state.aiming) return;
    state.aiming = false;
    placePoint(eventToVideo(e));
    if (state.touch) state.cursor = null;
    draw();
  });
  canvas.addEventListener("pointercancel", () => { state.aiming = false; state.cursor = null; draw(); });
  canvas.addEventListener("pointerleave", e => { if (e.pointerType === "mouse" && !state.aiming) { state.cursor = null; draw(); } });

  // --- Scrubber -------------------------------------------------------------
  const slider = el("input", { type: "range", min: 0, max: v.frame_count - 1, value: state.frame, class: "scrub", "aria-label": "Frame" });
  const frameLabel = el("span", { class: "frame-label" });
  slider.addEventListener("input", () => setFrame(Number(slider.value)));

  function setFrame(f) {
    state.frame = Math.max(0, Math.min(v.frame_count - 1, f));
    slider.value = state.frame;
    frameLabel.textContent = `Frame ${state.frame} · ${(state.frame / v.fps).toFixed(3)}s`;
    showFrame(state.frame);
  }
  const step = n => el("button", { class: "btn small", type: "button", onclick: () => setFrame(state.frame + n),
    title: `${n > 0 ? "Forward" : "Back"} ${Math.abs(n)} frame${Math.abs(n) > 1 ? "s" : ""}` },
  n === -10 ? "«" : n === -1 ? "‹" : n === 1 ? "›" : "»");

  // --- Sidebar --------------------------------------------------------------
  const pointList = el("ol", { class: "point-list" });
  const saveBtn = el("button", { class: "btn primary block", type: "button", onclick: save }, "Save marks");
  const saveError = el("div", { class: "notice error", hidden: true });

  function refresh() {
    const next = nextPoint();
    pointList.replaceChildren(...required.map(name => {
      const done = Boolean(state.points[name]);
      return el("li", { class: `${done ? "done" : ""} ${name === next ? "next" : ""}` },
        el("span", { class: "swatch", style: { background: POINT_INFO[name].color } }),
        el("div", {}, el("strong", {}, POINT_INFO[name].label), el("div", { class: "subtle small" }, POINT_INFO[name].hint)),
        el("span", { class: "check" }, done ? "✓" : name === next ? "Click it" : ""));
    }));
    saveBtn.disabled = Boolean(next);
    draw();
  }

  async function save() {
    saveError.hidden = true;
    saveBtn.disabled = true;
    try {
      await postJSON(`/api/swings/${encodeURIComponent(id)}/marks`, { address_frame: state.frame, points: state.points });
      location.hash = swingUrl(id);
    } catch (err) {
      saveError.textContent = err.message;
      saveError.hidden = false;
      saveBtn.disabled = false;
    }
  }

  // --- Trim -----------------------------------------------------------------
  const offset = v.trim_start || 0; // seconds into the original video where frame 0 is
  const trim = { start: v.trim_start, end: v.trim_end };
  const trimStatus = el("div", { class: "subtle small" });
  const trimBody = el("div", { class: "stack-sm" });
  function trimText() {
    const fmt = t => (t === null || t === undefined ? null : `${t.toFixed(2)}s`);
    trimStatus.textContent = `Keeping ${fmt(trim.start) || "the start"} to ${fmt(trim.end) || "the end"} of the original video.`;
  }
  const applyTrim = async (start, end) => {
    const progress = progressBlock("Re-cutting the clip");
    trimBody.replaceChildren(progress.node);
    try {
      const res = await postJSON(`/api/swings/${encodeURIComponent(id)}/trim`, { start, end });
      const job = await pollJob(res.job.id, j => progress.update(j.fraction, j.message), isCurrent);
      if (job && job.state === "failed") throw new Error(job.error);
      if (isCurrent()) await renderMark(view, id, isCurrent);
    } catch (err) {
      trimBody.replaceChildren(el("div", { class: "notice error" }, err.message));
    }
  };
  trimBody.append(
    trimStatus,
    el("div", { class: "actions" },
      el("button", { class: "btn small", type: "button", onclick: () => { trim.start = offset + state.frame / v.fps; trimText(); } }, "Start here"),
      el("button", { class: "btn small", type: "button", onclick: () => { trim.end = offset + (state.frame + 1) / v.fps; trimText(); } }, "End here")),
    el("div", { class: "actions" },
      el("button", { class: "btn small primary", type: "button", onclick: () => applyTrim(trim.start, trim.end) }, "Apply trim"),
      (v.trim_start !== null || v.trim_end !== null)
        ? el("button", { class: "btn small", type: "button", onclick: () => applyTrim(null, null) }, "Remove trim") : null),
    el("div", { class: "subtle small" }, "Re-cutting keeps your marked points but resets the frame."));
  trimText();

  // --- Keyboard -------------------------------------------------------------
  function onKey(e) {
    if (!isCurrent()) { document.removeEventListener("keydown", onKey); return; }
    if (e.target instanceof HTMLInputElement && e.target.type !== "range") return;
    if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
      e.preventDefault();
      setFrame(state.frame + (e.key === "ArrowLeft" ? -1 : 1) * (e.shiftKey ? 10 : 1));
    } else if (e.key === "Backspace" || e.key === "u") {
      e.preventDefault();
      undo();
    } else if (e.key === "Enter" && !nextPoint()) {
      save();
    }
  }
  document.addEventListener("keydown", onKey);
  const onResize = () => { if (isCurrent()) fitCanvas(); else window.removeEventListener("resize", onResize); };
  window.addEventListener("resize", onResize);

  // --- Render ---------------------------------------------------------------
  const intro = s.view === "dtl"
    ? "Scrub to your address position (set up and still), then click the points. This frame is used for the address checks."
    : "Scrub to your address position, then click the ball.";
  view.replaceChildren(
    swingHeader(s),
    el("div", { class: "mark-layout" },
      el("div", { class: "mark-main" },
        el("div", { class: "stage" }, canvas),
        el("div", { class: "scrub-row" }, step(-10), step(-1), slider, step(1), step(10)),
        el("div", { class: "subtle small center" }, frameLabel, " · ← → step, Shift = 10 frames")),
      el("aside", { class: "mark-side stack" },
        el("section", { class: "panel" },
          el("h2", {}, "Mark your address"),
          el("p", { class: "subtle small" }, intro),
          pointList,
          el("div", { class: "actions" },
            el("button", { class: "btn small", type: "button", onclick: undo }, "Undo"),
            el("button", { class: "btn small", type: "button", onclick: () => { state.points = {}; refresh(); } }, "Clear")),
          saveError, saveBtn),
        el("details", { class: "panel" },
          el("summary", {}, el("strong", {}, "Trim the clip")),
          el("p", { class: "subtle small" }, "Cut out practice swings or idle time. Scrub to a frame and set the start or end there."),
          trimBody))));
  setFrame(state.frame);
  refresh();
  requestAnimationFrame(fitCanvas);
}

function label(ctx, text, x, y, color, dpr) {
  ctx.font = `${600} ${13 * dpr}px system-ui, sans-serif`;
  ctx.lineWidth = 3 * dpr;
  ctx.strokeStyle = "rgba(0,0,0,0.85)";
  ctx.strokeText(text, x, y);
  ctx.fillStyle = color;
  ctx.fillText(text, x, y);
}
