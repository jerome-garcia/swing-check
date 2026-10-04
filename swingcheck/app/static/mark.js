import { api, el, features, pollJob, postJSON, progressBlock, swingUrl } from "./util.js";
import { swingHeader } from "./swing.js";

// Marking steps per view. Address is required; later checkpoints are optional and
// each has its own frame (the pose model can't see the club, so you click it).
const STEPS = {
  dtl: [
    { key: "address", title: "Address", points: ["ball", "clubhead", "grip"], optional: false,
      intro: "Scrub to your address position (set up and still), then click the points. This frame is used for the address checks." },
    { key: "takeaway", title: "Takeaway", points: ["clubhead"], optional: true,
      intro: "Scrub to where the shaft is parallel to the target line (from behind, it points at the camera). Click the clubhead. This frame is the takeaway checkpoint." },
    { key: "halfway_back", title: "Halfway back", points: ["clubhead", "grip"], optional: true,
      intro: "Scrub to where your front arm is parallel to the ground (hands about level with your front shoulder). Click the clubhead, then your hands. This frame is the halfway-back checkpoint." },
    { key: "top", title: "Top", points: ["clubhead", "grip"], optional: true,
      intro: "Scrub to the top of your backswing (the moment the club stops going back). Click the clubhead, then your hands. This frame is the top checkpoint." },
    { key: "downswing", title: "Downswing", points: ["clubhead"], optional: true,
      intro: "Scrub to where the shaft is parallel to the ground on the way down (hands about hip height). Click the clubhead. This frame is the downswing checkpoint." },
    { key: "follow_through", title: "Follow-through", points: ["clubhead", "grip"], optional: true,
      intro: "Scrub to where your back arm is parallel to the ground after impact (hands about shoulder height, the mirror of halfway back; if your arms are hidden, pick where the shaft looks about as steep as at halfway back). Click the clubhead, then your hands. This frame is the follow-through checkpoint." },
  ],
  fo: [
    { key: "address", title: "Address", points: ["ball"], optional: false,
      intro: "Scrub to your address position, then click the ball." },
  ],
};
// Label offsets (CSS px) keep the ball and clubhead labels apart; those points sit together.
// Shapes match the key frames: clubhead = circle, hands = square, ball = ring. Here they're
// outlines with a center dot, so you can still see exactly what you clicked.
const POINT_INFO = {
  ball: { label: "Ball", hint: "Center of the ball", color: "#ffffff", shape: "ring", dx: 13, dy: 20 },
  clubhead: { label: "Clubhead", hint: "Where the shaft meets the clubhead (the hosel)", color: "#ffffff", shape: "circle", dx: -70, dy: -10 },
  grip: { label: "Hands", hint: "Center of your hands on the shaft", color: "#ffffff", shape: "square", dx: 13, dy: -9 },
};
const PLANE_COLOR = "#ff00ff"; // the address shaft line is the swing plane, magenta as on the key frames
// Wording for points on a later checkpoint frame.
const STEP_POINT_INFO = {
  takeaway: {
    clubhead: { label: "Clubhead", hint: "Center of the clubhead" },
  },
  halfway_back: {
    clubhead: { label: "Clubhead", hint: "Center of the clubhead, or the highest point of the shaft you can see if it's out of frame" },
    grip: { label: "Hands", hint: "Center of your hands" },
  },
  top: {
    clubhead: { label: "Clubhead", hint: "Center of the clubhead, or the end of the shaft you can see if it's out of frame" },
    grip: { label: "Hands", hint: "Center of your hands" },
  },
  downswing: {
    clubhead: { label: "Clubhead", hint: "Center of the clubhead (it may be blurred: click the middle of the streak)" },
  },
  follow_through: {
    clubhead: { label: "Clubhead", hint: "Center of the clubhead, or the highest point of the shaft you can see if it's out of frame" },
    grip: { label: "Hands", hint: "Center of your hands, or the lowest point of the shaft you can see if they're hidden behind you" },
  },
};
// Where to start a checkpoint step that has no detected phase of its own.
const FRAME_GUESS = {
  // Lead arm parallel comes about 40% of the way from takeaway to the top.
  halfway_back: p => (p.takeaway !== undefined && p.top !== undefined ? p.takeaway + 0.4 * (p.top - p.takeaway) : undefined),
  // Shaft parallel coming down is about halfway from the early downswing to impact.
  downswing: p => (p.early_downswing !== undefined && p.impact !== undefined ? (p.early_downswing + p.impact) / 2 : undefined),
  // Trail arm parallel after impact: about as long after impact as the downswing took from the top.
  follow_through: p => (p.top !== undefined && p.impact !== undefined ? p.impact + 0.6 * (p.impact - p.top) : undefined),
};
const pointInfo = (step, name) => ({ ...POINT_INFO[name], ...((STEP_POINT_INFO[step] || {})[name] || {}) });
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
  const steps = STEPS[s.view];
  const marksValid = s.status === "marked" || s.status === "analyzed";
  const clampFrame = f => Math.max(0, Math.min(v.frame_count - 1, Math.round(f)));
  // Address point positions survive a re-trim or a view change (the camera didn't move),
  // so keep the ones this view uses as a starting point.
  const addressFrame = s.marks ? clampFrame(s.marks.address_frame) : 0;
  const stepState = {};
  for (const st of steps) {
    if (st.key === "address") {
      stepState.address = { frame: addressFrame, points: pick((s.marks && s.marks.points) || {}, st.points) };
      continue;
    }
    // Later checkpoints: saved marks (only if still valid for this trim), else the detected
    // frame from the last analysis, else a guess just after address.
    const saved = marksValid && s.marks && s.marks.checkpoints ? s.marks.checkpoints[st.key] : null;
    const phases = marksValid && s.analysis && s.analysis.phases ? s.analysis.phases : null;
    const detected = phases ? (phases[st.key] ?? (FRAME_GUESS[st.key] || (() => undefined))(phases)) : undefined;
    stepState[st.key] = {
      frame: clampFrame(saved ? saved.frame : detected !== undefined ? detected : addressFrame + 0.6 * v.fps),
      points: saved ? pick(saved.points, st.points) : {},
    };
  }
  const state = {
    active: "address",
    steps: stepState,
    cursor: null, // {x, y} in video pixels while hovering/aiming
    aiming: false,
    touch: false,
  };
  const stepDef = () => steps.find(st => st.key === state.active);
  const cur = () => state.steps[state.active];

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
    // Desktop: fit below the header so the scrubber stays in view. Phones (one column, the
    // page scrolls anyway): use most of the screen height so points are easier to hit.
    const narrow = window.matchMedia("(max-width: 820px)").matches;
    const maxH = narrow ? Math.max(320, window.innerHeight * 0.68) : Math.max(260, window.innerHeight - top - 100);
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
  // An outline mark (circle / square / ring) with a dark edge, plus a center dot for the
  // clubhead and hands so the clicked spot stays visible.
  function drawMark(c, shape, x, y, color, dpr) {
    const r = (shape === "ring" ? 9 : 7) * dpr;
    const path = () => {
      c.beginPath();
      if (shape === "square") c.rect(x - r, y - r, 2 * r, 2 * r);
      else c.arc(x, y, r, 0, Math.PI * 2);
    };
    c.lineWidth = 4 * dpr; c.strokeStyle = "rgba(0,0,0,0.8)"; path(); c.stroke();
    c.lineWidth = 2 * dpr; c.strokeStyle = color; path(); c.stroke();
    if (shape !== "ring") {
      c.fillStyle = "rgba(0,0,0,0.8)"; c.beginPath(); c.arc(x, y, 2.5 * dpr, 0, Math.PI * 2); c.fill();
      c.fillStyle = color; c.beginPath(); c.arc(x, y, 1.5 * dpr, 0, Math.PI * 2); c.fill();
    }
  }

  function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const img = full || preview;
    if (img) ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    const dpr = window.devicePixelRatio || 1;

    const points = cur().points;
    if (points.clubhead && points.grip) {
      // At address the shaft line is the swing plane (magenta); later, just the shaft (white).
      const [ax, ay] = toCanvas(...points.clubhead);
      const [bx, by] = toCanvas(...points.grip);
      ctx.strokeStyle = state.active === "address" ? PLANE_COLOR : "#ffffff";
      ctx.lineWidth = 2 * dpr;
      ctx.beginPath(); ctx.moveTo(ax, ay); ctx.lineTo(bx, by); ctx.stroke();
    }
    for (const name of stepDef().points) {
      const p = points[name];
      if (!p) continue;
      const [cx, cy] = toCanvas(...p);
      const info = pointInfo(state.active, name);
      drawMark(ctx, info.shape, cx, cy, info.color, dpr);
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
  const nextPoint = () => stepDef().points.find(n => !cur().points[n]) || null;
  const complete = key => steps.find(st => st.key === key).points.every(n => state.steps[key].points[n]);
  const started = key => Object.keys(state.steps[key].points).length > 0;

  function placePoint(p) {
    const name = nextPoint();
    if (!name) return;
    cur().points[name] = [Math.round(p.x * 10) / 10, Math.round(p.y * 10) / 10];
    refresh();
  }

  function undo() {
    const placed = stepDef().points.filter(n => cur().points[n]);
    if (placed.length) delete cur().points[placed[placed.length - 1]];
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
  const slider = el("input", { type: "range", min: 0, max: v.frame_count - 1, value: cur().frame, class: "scrub", "aria-label": "Frame" });
  const frameLabel = el("span", { class: "frame-label" });
  slider.addEventListener("input", () => setFrame(Number(slider.value)));

  function setFrame(f) {
    cur().frame = clampFrame(f);
    slider.value = cur().frame;
    frameLabel.textContent = `Frame ${cur().frame} · ${(cur().frame / v.fps).toFixed(3)}s`;
    showFrame(cur().frame);
  }
  const step = n => el("button", { class: "btn small", type: "button", onclick: () => setFrame(cur().frame + n),
    title: `${n > 0 ? "Forward" : "Back"} ${Math.abs(n)} frame${Math.abs(n) > 1 ? "s" : ""}` },
  n === -10 ? "«" : n === -1 ? "‹" : n === 1 ? "›" : "»");

  // --- Sidebar --------------------------------------------------------------
  const pointList = el("ol", { class: "point-list" });
  const stepIntro = el("p", { class: "subtle small" });
  const stepTabs = el("div", { class: "step-tabs", role: "tablist" });
  const saveBtn = el("button", { class: "btn primary block", type: "button", onclick: save }, "Save marks");
  const saveError = el("div", { class: "notice error", hidden: true });
  // Instruction bar over the frame: which step, what to click next, and what comes after.
  const hud = el("div", { class: "mark-hud", "aria-live": "polite" });

  function selectStep(key) {
    state.active = key;
    state.cursor = null;
    setFrame(cur().frame);
    refresh();
  }

  function renderHud(next) {
    const i = steps.findIndex(st => st.key === state.active);
    const after = steps[i + 1];
    const info = next ? pointInfo(state.active, next) : null;
    hud.replaceChildren(
      el("div", { class: "hud-text" },
        el("span", { class: "hud-step" }, steps.length > 1 ? `${i + 1}/${steps.length} · ${stepDef().title}` : stepDef().title),
        info
          ? el("span", { class: "hud-next" }, el("span", { class: `swatch ${info.shape}` }), `Click the ${info.label.toLowerCase()}`)
          : el("span", { class: "hud-next done" }, "✓ Done")),
      el("div", { class: "actions" },
        el("button", { class: "btn small", type: "button", onclick: undo, disabled: !started(state.active) }, "Undo"),
        !next && after ? el("button", { class: "btn small primary", type: "button", onclick: () => selectStep(after.key) }, `Next: ${after.title} ›`) : null,
        !next && !after && complete("address") ? el("button", { class: "btn small primary", type: "button", onclick: save }, "Save marks") : null));
  }

  function refresh() {
    const next = nextPoint();
    renderHud(next);
    stepTabs.replaceChildren(...steps.map(st => el("button", {
      type: "button", role: "tab", class: `step-tab ${st.key === state.active ? "selected" : ""} ${complete(st.key) ? "complete" : ""}`,
      "aria-selected": String(st.key === state.active), onclick: () => selectStep(st.key),
      title: st.optional ? "Optional" : "Required",
    },
    el("span", { class: "step-tab-state" }, complete(st.key) ? "✓" : started(st.key) ? "…" : st.optional ? "" : "•"),
    el("span", {}, st.title))));
    stepIntro.textContent = stepDef().intro;
    pointList.replaceChildren(...stepDef().points.map(name => {
      const done = Boolean(cur().points[name]);
      const info = pointInfo(state.active, name);
      return el("li", { class: `${done ? "done" : ""} ${name === next ? "next" : ""}` },
        el("span", { class: `swatch ${info.shape}` }),
        el("div", {}, el("strong", {}, info.label), el("div", { class: "subtle small" }, info.hint)),
        el("span", { class: "check" }, done ? "✓" : name === next ? "Click it" : ""));
    }));
    saveBtn.disabled = !complete("address");
    draw();
  }

  async function save() {
    saveError.hidden = true;
    const unfinished = steps.filter(st => st.optional && started(st.key) && !complete(st.key));
    if (unfinished.length) {
      saveError.textContent = `Finish or clear the ${unfinished.map(st => st.title.toLowerCase()).join(", ")} marks first.`;
      saveError.hidden = false;
      return;
    }
    const checkpoints = Object.fromEntries(steps.filter(st => st.optional && complete(st.key))
      .map(st => [st.key, { frame: state.steps[st.key].frame, points: state.steps[st.key].points }]));
    saveBtn.disabled = true;
    try {
      await postJSON(`/api/swings/${encodeURIComponent(id)}/marks`,
        { address_frame: state.steps.address.frame, points: state.steps.address.points, checkpoints });
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
      el("button", { class: "btn small", type: "button", onclick: () => { trim.start = offset + cur().frame / v.fps; trimText(); } }, "Start here"),
      el("button", { class: "btn small", type: "button", onclick: () => { trim.end = offset + (cur().frame + 1) / v.fps; trimText(); } }, "End here")),
    el("div", { class: "actions" },
      el("button", { class: "btn small primary", type: "button", onclick: () => applyTrim(trim.start, trim.end) }, "Apply trim"),
      (v.trim_start !== null || v.trim_end !== null)
        ? el("button", { class: "btn small", type: "button", onclick: () => applyTrim(null, null) }, "Remove trim") : null),
    el("div", { class: "subtle small" }, "Re-cutting keeps your marked points but resets the frame."));
  trimText();

  // --- Camera view ----------------------------------------------------------
  const viewError = el("div", { class: "notice error", hidden: true });
  const { face_on: faceOn, face_on_message: faceOnMessage } = await features();
  if (!isCurrent()) return;
  const viewButtons = ["dtl", "fo"].map(choice => el("button", {
    type: "button", class: `btn small ${choice === s.view ? "selected" : ""}`, "aria-pressed": String(choice === s.view),
    disabled: choice === "fo" && !faceOn && s.view !== "fo",
    title: choice === "fo" && !faceOn ? faceOnMessage : null,
    onclick: async () => {
      if (choice === s.view) return;
      if (marksValid && !confirm("Switching the view means marking this swing again for that view. Continue?")) return;
      try {
        await postJSON(`/api/swings/${encodeURIComponent(id)}/view`, { view: choice });
        if (isCurrent()) await renderMark(view, id, isCurrent);
      } catch (err) {
        viewError.textContent = err.message;
        viewError.hidden = false;
      }
    },
  }, choice === "dtl" ? "Down-the-line" : "Face-on"));

  // --- Keyboard -------------------------------------------------------------
  function onKey(e) {
    if (!isCurrent()) { document.removeEventListener("keydown", onKey); return; }
    if (e.target instanceof HTMLInputElement && e.target.type !== "range") return;
    if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
      e.preventDefault();
      setFrame(cur().frame + (e.key === "ArrowLeft" ? -1 : 1) * (e.shiftKey ? 10 : 1));
    } else if (e.key === "Backspace" || e.key === "u") {
      e.preventDefault();
      undo();
    } else if (e.key === "Enter" && complete("address")) {
      save();
    }
  }
  document.addEventListener("keydown", onKey);
  const onResize = () => { if (isCurrent()) fitCanvas(); else window.removeEventListener("resize", onResize); };
  window.addEventListener("resize", onResize);

  // --- Render ---------------------------------------------------------------
  view.replaceChildren(
    swingHeader(s, s.status === "analyzed" ? [el("a", { class: "btn", href: swingUrl(id) }, "Back to results")] : []),
    el("div", { class: "mark-layout" },
      el("div", { class: "mark-main" },
        hud,
        el("div", { class: "stage" }, canvas),
        el("div", { class: "scrub-row" }, step(-10), step(-1), slider, step(1), step(10)),
        el("div", { class: "subtle small center frame-caption" }, frameLabel, el("span", { class: "keys-hint" }, " · ← → step, Shift = 10 frames"))),
      el("aside", { class: "mark-side stack" },
        el("section", { class: "panel" },
          el("h2", {}, steps.length > 1 ? "Mark your swing" : "Mark your address"),
          steps.length > 1 ? el("p", { class: "subtle small" }, "Address is required (•); the other steps are optional, one per checkpoint.") : null,
          steps.length > 1 ? stepTabs : null,
          stepIntro,
          pointList,
          el("div", { class: "actions" },
            el("button", { class: "btn small", type: "button", onclick: undo }, "Undo"),
            el("button", { class: "btn small", type: "button", onclick: () => { cur().points = {}; refresh(); } }, "Clear step")),
          saveError, saveBtn),
        el("details", { class: "panel" },
          el("summary", {}, el("strong", {}, "Trim the clip")),
          el("p", { class: "subtle small" }, "Cut out practice swings or idle time. Scrub to a frame and set the start or end there."),
          trimBody),
        el("details", { class: "panel" },
          el("summary", {}, el("strong", {}, "Camera view"), el("span", { class: "subtle small" }, ` · ${s.view === "fo" ? "Face-on" : "Down-the-line"}`)),
          el("div", { class: "actions" }, viewButtons),
          !faceOn ? el("p", { class: "subtle small" }, faceOnMessage) : null,
          viewError))));
  setFrame(cur().frame);
  refresh();
  requestAnimationFrame(fitCanvas);
}

function pick(points, names) {
  return Object.fromEntries(Object.entries(points).filter(([n]) => names.includes(n)));
}

function label(ctx, text, x, y, color, dpr) {
  ctx.font = `${600} ${13 * dpr}px system-ui, sans-serif`;
  ctx.lineWidth = 3 * dpr;
  ctx.strokeStyle = "rgba(0,0,0,0.85)";
  ctx.strokeText(text, x, y);
  ctx.fillStyle = color;
  ctx.fillText(text, x, y);
}
