import { api, el, features, HAND_NAMES, listText, pollJob, postJSON, progressBlock, swingUrl } from "./util.js";
import { swingHeader } from "./swing.js";

// Marking steps per view, all required. After address, one step per checkpoint, and
// each has its own frame (the pose model can't see the club, so you click it).
const STEPS = {
  dtl: [
    { key: "address", title: "Address", points: ["ball", "clubhead", "grip"],
      intro: "Move the slider to your address position (set up and still), then click the points. This frame is used for the address checks." },
    { key: "takeaway", title: "Takeaway", points: ["clubhead"],
      intro: "Move the slider to where the shaft is parallel to the target line (from behind, it points at the camera). Click the clubhead. This frame is the takeaway checkpoint." },
    { key: "halfway_back", title: "Halfway back", points: ["clubhead", "grip"],
      intro: "Move the slider to where your front arm is parallel to the ground (hands about level with your front shoulder). Click the clubhead, then your hands. This frame is the halfway-back checkpoint." },
    { key: "top", title: "Top", points: ["clubhead", "grip"],
      intro: "Move the slider to the top of your backswing (the moment the club stops going back). Click the clubhead, then your hands. This frame is the top checkpoint." },
    { key: "downswing", title: "Downswing", points: ["clubhead"],
      intro: "Move the slider to where the shaft is parallel to the ground on the way down (hands about hip height). Click the clubhead. This frame is the downswing checkpoint." },
    { key: "follow_through", title: "Follow-through", points: ["clubhead", "grip"],
      intro: "Move the slider to where your back arm is parallel to the ground after impact (hands about shoulder height, the mirror of halfway back; if your arms are hidden, pick where the shaft looks about as steep as at halfway back). Click the clubhead, then your hands. This frame is the follow-through checkpoint." },
  ],
  fo: [
    { key: "address", title: "Address", points: ["ball"],
      intro: "Move the slider to your address position, then click the ball." },
  ],
};
// Label offsets (CSS px) keep the ball and clubhead labels apart; those points sit together.
// Shapes match the key frames: clubhead = circle, hands = square, ball = ring. Here they're
// outlines with a center dot, so you can still see exactly what you clicked.
const POINT_INFO = {
  ball: { label: "Ball", hint: "Center of the ball", color: "#ffffff", shape: "ring", dx: 13, dy: 20 },
  // At address the point is the club neck, not the clubface: the shaft line through it is the swing plane.
  clubhead: { label: "Club neck", hint: "Where the shaft goes into the clubhead (the hosel)", color: "#ffffff", shape: "circle", dx: -70, dy: -10 },
  grip: { label: "Hands", hint: "Middle of your grip, between your two hands", color: "#ffffff", shape: "square", dx: 13, dy: -9 },
};
const REFERENCE_DIR = "reference"; // static/reference: the example swing shown beside each step
const PLANE_COLOR = "#ff9f43"; // the address shaft line is the swing plane, in the brand's plane orange
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
// Where to start a checkpoint step that has no detected phase of its own (checked against
// hand-marked McIlroy, Tiger and amateur clips).
const FRAME_GUESS = {
  // Lead arm parallel comes about 30% of the way from takeaway to the top.
  halfway_back: p => (p.takeaway !== undefined && p.top !== undefined ? p.takeaway + 0.3 * (p.top - p.takeaway) : undefined),
  // Shaft parallel coming down is about halfway from the early downswing to impact.
  downswing: p => (p.early_downswing !== undefined && p.impact !== undefined ? (p.early_downswing + p.impact) / 2 : undefined),
  // Trail arm parallel after impact: about as long after impact as the downswing took from the top.
  follow_through: p => (p.top !== undefined && p.impact !== undefined ? p.impact + 0.6 * (p.impact - p.top) : undefined),
};
// The camera check made after upload (swingcheck/camera_check.py): what to film
// differently, or a short all-clear. Nothing for older swings or face-on.
function cameraCheck(s) {
  const found = s.camera_check;
  if (s.view !== "dtl" || !Array.isArray(found)) return null;
  if (!found.length) return el("p", { class: "camera-ok" }, "✓ Camera check: a good down-the-line view.");
  const serious = found.some(f => f.level === "flag");
  return el("details", { class: `notice camera-check ${serious ? "error" : ""}`, open: true },
    el("summary", {}, `Camera check: ${found.length === 1 ? "1 thing" : `${found.length} things`} to film differently`),
    el("ul", {}, found.map(f => el("li", {}, el("strong", {}, `${f.title}. `), f.tip))),
    el("p", { class: "small" }, serious
      ? "Results from this video will likely be wrong. Film again and upload the new video for a real check."
      : "You can still mark this video, but some results may be off."));
}

const pointInfo = (step, name) => ({ ...POINT_INFO[name], ...((STEP_POINT_INFO[step] || {})[name] || {}) });
const LOUPE_SIZE = 150;
const LOUPE_ZOOM = 4;

export async function renderMark(view, id, isCurrent) {
  const [s, reference] = await Promise.all([
    api(`/api/swings/${encodeURIComponent(id)}`),
    api(`${REFERENCE_DIR}/reference.json`).catch(() => null),
  ]);
  if (!isCurrent()) return;
  if (!s.video || (s.job && ["queued", "running"].includes(s.job.state))) {
    location.replace(swingUrl(id));
    return;
  }

  const v = s.video;
  const steps = STEPS[s.view];
  const marksValid = s.status === "marked" || s.status === "analyzed";
  const clampFrame = f => Math.max(0, Math.min(v.frame_count - 1, Math.round(f)));
  // Where each step opens: the frames from the last analysis, else the suggestions found
  // right after conversion (a quick pass over the clip), else a guess just after address.
  const phases = (marksValid && s.analysis && s.analysis.phases) || s.suggested || null;
  const phaseFrame = key => (phases ? (phases[key] ?? (FRAME_GUESS[key] || (() => undefined))(phases)) : undefined);
  // Address point positions survive a re-trim or a view change (the camera didn't move),
  // so keep the ones this view uses as a starting point. The frame only if it still fits.
  const savedAddress = Boolean(s.marks) && (marksValid || !s.suggested);
  const addressSuggested = !savedAddress && s.suggested ? clampFrame(s.suggested.address) : undefined;
  const addressFrame = savedAddress ? clampFrame(s.marks.address_frame) : addressSuggested ?? 0;
  const stepState = {};
  for (const st of steps) {
    if (st.key === "address") {
      stepState.address = { frame: addressFrame, suggested: addressSuggested,
        points: pick((s.marks && s.marks.points) || {}, st.points) };
      continue;
    }
    // Later checkpoints: saved marks (only if still valid for this trim), else where it opens.
    const saved = marksValid && s.marks && s.marks.checkpoints ? s.marks.checkpoints[st.key] : null;
    const detected = phaseFrame(st.key);
    const suggested = !saved && detected !== undefined ? clampFrame(detected) : undefined;
    stepState[st.key] = {
      frame: clampFrame(saved ? saved.frame : suggested ?? addressFrame + 0.6 * v.fps),
      suggested,
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
  // Each frame is a round trip to the server, so: one request at a time with the newest
  // frame winning (dragging the slider never queues up frames already passed), frames kept
  // here and in the browser's cache (going back is instant), and once a frame settles, its
  // neighbours load quietly so stepping with ‹ › or the arrow keys doesn't wait.
  const images = new Map(); // url -> loaded image, least recently used first
  const KEEP_IMAGES = 150;
  const NEIGHBOURS = [1, -1, 2, -2, 3, -3, 10, -10]; // the step buttons: 1 and 10
  let wanted = null; // frame waiting to be fetched
  let fetching = false;
  let settleTimer = null;
  let settleToken = 0;

  // The preview is scaled to the canvas; at or above the video's own width it's the full frame.
  const previewWidth = () => (Math.round(canvas.width || 720) >= v.width ? null : Math.round(canvas.width || 720));

  function frameUrl(frame, width) {
    const query = new URLSearchParams();
    if (width) query.set("w", width);
    if (v.version) query.set("c", v.version); // this conversion: lets the browser cache the frame
    const qs = query.toString();
    return `/api/swings/${encodeURIComponent(id)}/frames/${frame}.jpg${qs ? `?${qs}` : ""}`;
  }

  function cached(url) {
    const img = images.get(url);
    if (img) { images.delete(url); images.set(url, img); } // now the most recently used
    return img || null;
  }

  function loadImage(url) {
    const hit = cached(url);
    if (hit) return Promise.resolve(hit);
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => {
        images.set(url, img);
        if (images.size > KEEP_IMAGES) images.delete(images.keys().next().value);
        resolve(img);
      };
      img.onerror = () => reject(new Error("frame failed to load"));
      img.src = url;
    });
  }

  function display(frame, img) {
    const width = previewWidth();
    preview = img;
    full = width ? cached(frameUrl(frame)) : img;
    draw();
    clearTimeout(settleTimer);
    settleTimer = setTimeout(() => settle(frame), 200);
  }

  function showFrame(frame) {
    ++settleToken; // stop loading the old frame's neighbours
    clearTimeout(settleTimer);
    const hit = cached(frameUrl(frame, previewWidth()));
    if (hit) { wanted = null; display(frame, hit); return; }
    full = null;
    wanted = frame;
    fetchWanted();
  }

  async function fetchWanted() {
    if (fetching) return; // the running loop picks up the newest wanted frame
    fetching = true;
    while (wanted !== null) {
      const frame = wanted;
      wanted = null;
      const img = await loadImage(frameUrl(frame, previewWidth())).catch(() => null); // null: the server is busy
      if (img && wanted === null && frame === cur().frame) display(frame, img);
    }
    fetching = false;
  }

  // Once the frame stays put: full resolution for precise aiming (if the preview is
  // scaled), then the neighbours, one at a time, stopping as soon as the frame changes.
  async function settle(frame) {
    const token = ++settleToken;
    const width = previewWidth();
    if (width) {
      const big = await loadImage(frameUrl(frame)).catch(() => null);
      if (token !== settleToken) return;
      if (big && frame === cur().frame) { full = big; draw(); }
    }
    for (const d of NEIGHBOURS) {
      if (token !== settleToken) return;
      const f = frame + d;
      if (f >= 0 && f < v.frame_count) await loadImage(frameUrl(f, width)).catch(() => null);
    }
  }

  // --- Layout ---------------------------------------------------------------
  // Page offset that the sticky top bar covers, plus a little air.
  const stickyTop = () => (document.querySelector(".topbar")?.offsetHeight || 0) + 12;

  // Once, on opening: scroll so the instruction bar sits under the top bar, if the frame and
  // slider don't fit as is. Not when the camera check found problems: those stay in view.
  function scrollToMarking() {
    if (window.matchMedia("(max-width: 820px)").matches) return;
    if (Array.isArray(s.camera_check) && s.camera_check.length) return;
    const caption = view.querySelector(".frame-caption");
    if (!caption || caption.getBoundingClientRect().bottom <= window.innerHeight) return;
    window.scrollTo({ top: hud.getBoundingClientRect().top + window.scrollY - stickyTop() });
  }

  function fitCanvas() {
    const stage = canvas.parentElement;
    if (!stage) return;
    const maxW = stage.clientWidth;
    // Desktop: fit the instruction bar, the frame and the slider (with its caption, ~100 px)
    // in one screen with the page scrolled to the bar (scrollToMarking), so a tall phone
    // video isn't squeezed by the swing header above. Phones (one column, the page scrolls
    // anyway): use most of the screen height so points are easier to hit.
    const narrow = window.matchMedia("(max-width: 820px)").matches;
    const hudToStage = stage.getBoundingClientRect().top - hud.getBoundingClientRect().top;
    const maxH = narrow ? Math.max(320, window.innerHeight * 0.68)
      : Math.max(260, window.innerHeight - stickyTop() - hudToStage - 100);
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
      // At address the shaft line is the swing plane (orange); later, just the shaft (white).
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
  const unfinished = () => steps.filter(st => !complete(st.key));

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

  // The step opened on a suggested frame: say so, and offer a way back to it after scrubbing.
  const suggestedTag = el("span", { class: "suggested-tag", hidden: true,
    title: "Found automatically. Check it and move the slider to the exact frame if needed." }, "Suggested frame");
  const backToSuggested = el("button", { class: "linkish", type: "button", hidden: true,
    onclick: () => setFrame(cur().suggested) }, "Back to the suggested frame");
  // A quiet reminder under the scrubber: the suggestion is a guess, the exact frame is theirs to pick.
  const suggestNote = el("p", { class: "suggest-note", hidden: true });

  function setFrame(f) {
    cur().frame = clampFrame(f);
    slider.value = cur().frame;
    frameLabel.textContent = `Frame ${cur().frame} · ${(cur().frame / v.fps).toFixed(3)}s`;
    const onSuggestion = cur().suggested !== undefined && cur().frame === cur().suggested;
    suggestedTag.hidden = !onSuggestion;
    backToSuggested.hidden = onSuggestion || cur().suggested === undefined;
    suggestNote.hidden = cur().suggested === undefined;
    suggestNote.textContent = `This opens on a suggested frame, a best guess at your ${stepDef().title.toLowerCase()}. `
      + "Check it, and move the slider to the exact frame if it's off.";
    showFrame(cur().frame);
    refresh(); // the frame-order check and the step tabs depend on the frame
  }
  const step = n => el("button", { class: "btn small", type: "button", onclick: () => setFrame(cur().frame + n),
    title: `${n > 0 ? "Forward" : "Back"} ${Math.abs(n)} frame${Math.abs(n) > 1 ? "s" : ""}` },
  n === -10 ? "«" : n === -1 ? "‹" : n === 1 ? "›" : "»");

  // --- Reference swing ------------------------------------------------------
  // Rory McIlroy in the same position, with his marks, next to the step's instructions
  // (frames built by swingcheck/app/make_reference.py).
  const refBox = el("figure", { class: "ref-frame" });
  let refShown = null; // the step it's showing; redraw only on a step change
  function renderRef() {
    if (refShown === state.active) return;
    refShown = state.active;
    const st = s.view === "dtl" && reference ? reference.steps[state.active] : null;
    refBox.hidden = !st;
    if (!st) return;
    const url = `${REFERENCE_DIR}/${st.image}`;
    const { width: w, height: h } = reference;
    const r = Math.max(w, h) / 55;
    const p = pick(st.points, stepDef().points); // only what this step asks you to click
    const shaft = p.clubhead && p.grip
      ? `<line x1="${p.clubhead[0]}" y1="${p.clubhead[1]}" x2="${p.grip[0]}" y2="${p.grip[1]}" stroke="${state.active === "address" ? PLANE_COLOR : "#fff"}" stroke-width="${r / 4}"/>` : "";
    const mark = (name, [x, y]) => {
      const outline = POINT_INFO[name].shape === "square"
        ? `<rect x="${x - r}" y="${y - r}" width="${2 * r}" height="${2 * r}"/>` : `<circle cx="${x}" cy="${y}" r="${r}"/>`;
      return `<g fill="none"><g stroke="rgba(0,0,0,.8)" stroke-width="${r / 1.8}">${outline}</g>`
        + `<g stroke="#fff" stroke-width="${r / 3.5}">${outline}</g></g>`;
    };
    const link = el("a", { href: url, target: "_blank", rel: "noopener", title: "Open full size" });
    // A right-handed example, mirrored for a left-handed golfer so it matches their view.
    const mirror = s.handedness === "left" ? ` transform="translate(${w} 0) scale(-1 1)"` : "";
    link.innerHTML = `<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="Reference frame"><g${mirror}>`
      + `<image href="${url}" width="${w}" height="${h}"/>${shaft}`
      + Object.entries(p).filter(([n]) => POINT_INFO[n]).map(([n, pt]) => mark(n, pt)).join("") + "</g></svg>";
    // Labelled as an example on the picture itself too, so it's never mistaken for your swing.
    link.append(el("span", { class: "ref-tag" }, "Example"));
    refBox.replaceChildren(
      el("div", { class: "ref-head" }, el("strong", {}, "Example to follow"),
        el("div", { class: "subtle small" }, `${reference.name} at ${stepDef().title.toLowerCase()}`
          + (s.handedness === "left" ? " (mirrored to match a left-handed swing)" : "")
          + ", for comparison. Not your swing: mark yours on your own video.")),
      link);
  }

  // --- Mark checks ----------------------------------------------------------
  // Quick sanity checks on the marks; they warn but never block saving.
  const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);
  function markWarnings() {
    const out = []; // [stepKey, sentence]
    const a = state.steps.address.points;
    if (a.clubhead && a.grip && a.grip[1] >= a.clubhead[1]) {
      out.push(["address", "Your hands should be above the club neck. Check you clicked the club neck first, then your hands."]);
    }
    const shaft = a.clubhead && a.grip ? dist(a.clubhead, a.grip) : null;
    if (a.ball && a.clubhead && shaft && dist(a.ball, a.clubhead) > 0.5 * shaft) {
      out.push(["address", "The club neck should sit just behind the ball. Check the ball and club neck marks."]);
    }
    let prev = steps[0];
    for (const st of steps.slice(1)) {
      if (!started(st.key)) continue;
      const here = state.steps[st.key];
      if (here.frame <= state.steps[prev.key].frame) {
        out.push([st.key, `This ${st.title.toLowerCase()} frame comes before your ${prev.title.toLowerCase()} frame. Check the frame.`]);
      }
      const p = here.points;
      if (p.clubhead && p.grip) {
        if (["halfway_back", "follow_through"].includes(st.key) && p.clubhead[1] >= p.grip[1]) {
          out.push([st.key, "The clubhead should be above your hands here. Check you clicked the clubhead first, then your hands."]);
        }
        // From behind, the club looks shorter at address (it leans away from the camera) than
        // upright at halfway back: real marks reach 1.5x, so only flag what can't be the club.
        if (shaft && dist(p.clubhead, p.grip) > 2 * shaft) {
          out.push([st.key, "The clubhead looks too far from your hands. Check the clubhead and hands marks."]);
        }
      }
      prev = st;
    }
    return out;
  }
  const warningBox = el("div", { class: "notice warn mark-warnings", hidden: true });
  function refreshWarnings() {
    const here = markWarnings().filter(([key]) => key === state.active).map(([, text]) => text);
    warningBox.hidden = !here.length;
    warningBox.replaceChildren(...here.map(text => el("p", {}, text)));
  }

  // --- Sidebar --------------------------------------------------------------
  const pointList = el("ol", { class: "point-list" });
  const stepIntro = el("p", { class: "subtle small" });
  const stepTabs = el("div", { class: "step-tabs", role: "tablist" });
  const saveBtn = el("button", { class: "btn primary block", type: "button", onclick: save }, "Save and analyze");
  const saveError = el("div", { class: "notice error", hidden: true });
  const saveHint = el("p", { class: "subtle small save-hint" });
  // Instruction bar over the frame: which step, what to click next, and what comes after.
  const hud = el("div", { class: "mark-hud", "aria-live": "polite" });

  function selectStep(key) {
    state.active = key;
    state.cursor = null;
    setFrame(cur().frame);
    refresh();
  }

  let hudShown = null; // the step and point the bar last asked for, to flash it on a change
  function renderHud(next) {
    const i = steps.findIndex(st => st.key === state.active);
    const after = steps[i + 1];
    const info = next ? pointInfo(state.active, next) : null;
    const doneHint = after ? `Next step: ${after.title}.`
      : unfinished().length ? `Still to mark: ${unfinished()[0].title.toLowerCase()}.` : "Every step is marked.";
    hud.replaceChildren(
      el("div", { class: "hud-text" },
        el("span", { class: "hud-step" }, steps.length > 1 ? `Step ${i + 1} of ${steps.length} · ${stepDef().title}` : stepDef().title),
        info
          ? el("span", { class: "hud-next" }, el("span", { class: `swatch ${info.shape}` }), `Click the ${info.label.toLowerCase()}`)
          : el("span", { class: "hud-next done" }, "✓ Step done"),
        el("span", { class: "hud-hint" }, info ? info.hint : doneHint)),
      el("div", { class: "actions" },
        el("button", { class: "btn small hud-btn", type: "button", onclick: undo, disabled: !started(state.active) }, "Undo"),
        el("button", { class: "btn small hud-btn", type: "button", disabled: !started(state.active),
          onclick: () => { cur().points = {}; refresh(); } }, "Clear step"),
        !next && after ? el("button", { class: "btn small primary", type: "button", onclick: () => selectStep(after.key) }, `Next: ${after.title} ›`) : null,
        // Last step done: save once every step is marked, else go back to the first one left.
        !next && !after && !unfinished().length ? el("button", { class: "btn small primary", type: "button", onclick: save }, "Save and analyze") : null,
        !next && !after && unfinished().length
          ? el("button", { class: "btn small primary", type: "button", onclick: () => selectStep(unfinished()[0].key) }, `Finish: ${unfinished()[0].title} ›`) : null));
    // A new instruction flashes once, so it's noticed.
    const shown = `${state.active}:${next || "done"}`;
    if (hudShown !== null && shown !== hudShown) {
      hud.classList.remove("flash");
      void hud.offsetWidth; // restart the animation
      hud.classList.add("flash");
    }
    hudShown = shown;
  }

  function refresh() {
    const next = nextPoint();
    renderHud(next);
    const warned = new Set(markWarnings().map(([key]) => key));
    // Numbered badges read as progress: the step number, ✓ once marked, ! if a mark looks off.
    stepTabs.replaceChildren(...steps.map((st, i) => {
      const done = complete(st.key);
      const status = warned.has(st.key) ? "warned" : done ? "complete" : started(st.key) ? "started" : "";
      return el("button", {
        type: "button", role: "tab", class: `step-tab ${st.key === state.active ? "selected" : ""} ${status}`,
        "aria-selected": String(st.key === state.active), onclick: () => selectStep(st.key),
        title: { warned: "Check this step's marks", complete: "Marked", started: "Started" }[status] || "Still to mark",
      },
      el("span", { class: "step-tab-state", "aria-hidden": "true" }, status === "warned" ? "!" : done ? "✓" : String(i + 1)),
      el("span", {}, st.title));
    }));
    stepIntro.textContent = stepDef().intro;
    pointList.replaceChildren(...stepDef().points.map(name => {
      const done = Boolean(cur().points[name]);
      const info = pointInfo(state.active, name);
      return el("li", { class: `${done ? "done" : ""} ${name === next ? "next" : ""}` },
        el("span", { class: `swatch ${info.shape}` }),
        el("div", {}, el("strong", {}, info.label), el("div", { class: "subtle small" }, info.hint)),
        el("span", { class: "check" }, done ? "✓" : name === next ? "Click it" : ""));
    }));
    saveBtn.disabled = unfinished().length > 0;
    saveHint.textContent = unfinished().length
      ? `Still to mark: ${listText(unfinished().map(st => st.title.toLowerCase()))}.` : "";
    renderRef();
    refreshWarnings();
    draw();
  }

  async function save() {
    saveError.hidden = true;
    const left = unfinished();
    if (left.length) {
      saveError.textContent = `Mark every step first. Still to mark: ${listText(left.map(st => st.title.toLowerCase()))}.`;
      saveError.hidden = false;
      return;
    }
    const warnings = markWarnings();
    if (warnings.length) {
      const titles = [...new Set(warnings.map(([key]) => steps.find(st => st.key === key).title))];
      const list = warnings.map(([, t]) => `• ${t}`).join("\n");
      if (!confirm(`Some marks look off (${titles.join(", ")}):\n\n${list}\n\nSave and analyze anyway?`)) return;
    }
    const checkpoints = Object.fromEntries(steps.filter(st => st.key !== "address")
      .map(st => [st.key, { frame: state.steps[st.key].frame, points: state.steps[st.key].points }]));
    saveBtn.disabled = true;
    try {
      await postJSON(`/api/swings/${encodeURIComponent(id)}/marks`,
        { address_frame: state.steps.address.frame, points: state.steps.address.points, checkpoints });
      // Analyze straight away; the swing page shows the job's progress. If it can't start,
      // the marks are still saved and the swing page offers Analyze.
      try { await postJSON(`/api/swings/${encodeURIComponent(id)}/analyze`, {}); } catch { /* see above */ }
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

  // --- Golfer: right- or left-handed -----------------------------------------
  // Marks stay (they're points on the video); an analyzed swing is analyzed again.
  const handButtons = ["right", "left"].map(choice => el("button", {
    type: "button", class: `btn small ${choice === s.handedness ? "selected" : ""}`,
    "aria-pressed": String(choice === s.handedness),
    onclick: async () => {
      if (choice === s.handedness) return;
      if (s.status === "analyzed" && !confirm(`Switch to ${HAND_NAMES[choice].toLowerCase()}? Your marks stay; `
          + "save and analyze again to update the results.")) return;
      try {
        await postJSON(`/api/swings/${encodeURIComponent(id)}/handedness`, { handedness: choice });
        if (isCurrent()) await renderMark(view, id, isCurrent);
      } catch (err) {
        viewError.textContent = err.message;
        viewError.hidden = false;
      }
    },
  }, HAND_NAMES[choice]));

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
    } else if (e.key === "Enter" && !unfinished().length) {
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
        cameraCheck(s),
        hud,
        el("div", { class: "stage" }, canvas),
        el("div", { class: "scrub-row" }, step(-10), step(-1), slider, step(1), step(10)),
        suggestNote,
        el("div", { class: "subtle small center frame-caption" }, frameLabel, " ", suggestedTag, " ", backToSuggested,
          el("span", { class: "keys-hint" }, " · ← → step, Shift = 10 frames"))),
      el("aside", { class: "mark-side stack" },
        el("section", { class: "panel" },
          el("h2", {}, steps.length > 1 ? "Mark your swing" : "Mark your address"),
          steps.length > 1 ? el("p", { class: "subtle small" }, `Mark all ${steps.length} steps, one per checkpoint.`) : null,
          steps.length > 1 ? stepTabs : null,
          stepIntro,
          pointList,
          warningBox,
          saveError, saveBtn, saveHint,
          // The example comes last, so the points to click and Save stay in view.
          refBox),
        el("details", { class: "panel" },
          el("summary", {}, el("strong", {}, "Trim the clip")),
          el("p", { class: "subtle small" }, "Cut out practice swings or idle time. Move the slider to a frame and set the start or end there."),
          trimBody),
        el("details", { class: "panel" },
          el("summary", {}, el("strong", {}, "Golfer"), el("span", { class: "subtle small" }, ` · ${HAND_NAMES[s.handedness] || HAND_NAMES.right}`)),
          el("div", { class: "actions" }, handButtons)),
        el("details", { class: "panel" },
          el("summary", {}, el("strong", {}, "Camera view"), el("span", { class: "subtle small" }, ` · ${s.view === "fo" ? "Face-on" : "Down-the-line"}`)),
          el("div", { class: "actions" }, viewButtons),
          !faceOn ? el("p", { class: "subtle small" }, faceOnMessage) : null,
          viewError))));
  setFrame(cur().frame);
  refresh();
  requestAnimationFrame(() => { fitCanvas(); scrollToMarking(); });
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
