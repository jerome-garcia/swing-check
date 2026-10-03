import { el, features, fileUrl, pollJob, postJSON, progressBlock, swingUrl } from "./util.js";

const STATUS_WORD = { ok: "OK", warn: "Watch", flag: "Flag", error: "No data" };
const PHASE_LABELS = {
  address: "Address", takeaway: "Takeaway", top: "Top", early_downswing: "Early downswing", impact: "Impact",
};
// Phases the user can set directly; the others are worked out between them.
const ADJUSTABLE = { dtl: ["top", "impact"], fo: ["address", "top", "impact"] };
const HIDDEN_MEASUREMENTS = new Set(["units", "traceback"]);

function prettyKey(key) {
  const s = key.replace(/_/g, " ").replace(/\bdeg\b/, "(°)");
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function prettyValue(v) {
  if (v === null || v === undefined) return "–";
  if (typeof v === "number") return Number.isInteger(v) ? String(v) : v.toFixed(Math.abs(v) < 1 ? 3 : 1);
  return String(v);
}

// One compact line per measurement: status dot, name, value, short verdict.
// Checks that don't supply rows (older analyses, face-on) fall back to their raw measurements.
function measurementRows(v) {
  if (v.rows && v.rows.length) return v.rows;
  return Object.entries(v.measurements || {}).filter(([k]) => !HIDDEN_MEASUREMENTS.has(k))
    .map(([k, val]) => ({ label: prettyKey(k), value: prettyValue(val), note: "", status: null }));
}

function verdictCard(v) {
  const rows = measurementRows(v);
  return el("article", { class: `verdict ${v.status}` },
    el("div", { class: "verdict-head" },
      el("h3", {}, v.title),
      el("span", { class: `status-pill ${v.status}` }, STATUS_WORD[v.status] || v.status)),
    el("div", { class: "verdict-label" }, v.label),
    el("p", { class: "verdict-summary" }, v.summary),
    rows.length ? el("ul", { class: "rows" }, rows.map(r => el("li", {},
      r.status ? el("span", { class: `dot ${r.status}`, title: STATUS_WORD[r.status] }) : el("span", {}),
      el("span", { class: "row-label" }, r.label),
      el("span", { class: "row-value" }, r.value),
      el("span", { class: "row-note" }, r.note)))) : null);
}

// --- Checkpoint stepper (down-the-line) ---------------------------------------
function checkpointStepper(s, checkpoints) {
  const verdicts = Object.fromEntries(((s.analysis && s.analysis.verdicts) || []).map(v => [v.name, v]));
  const stateOf = cp => (!cp.built ? "soon" : verdicts[cp.analyzer] ? verdicts[cp.analyzer].status : "missing");
  const STATE_WORD = { soon: "coming soon", missing: "not run yet", ...STATUS_WORD };
  // Start on the first flagged checkpoint, else the first one that has a result.
  let index = Math.max(0, checkpoints.findIndex(cp => stateOf(cp) === "flag"));
  if (stateOf(checkpoints[index]) !== "flag") index = Math.max(0, checkpoints.findIndex(cp => verdicts[cp.analyzer]));

  const chips = checkpoints.map((cp, i) => el("button", {
    type: "button", class: `step ${stateOf(cp)}`, title: `${cp.title}: ${STATE_WORD[stateOf(cp)]}`,
    onclick: () => select(i),
  }, el("span", { class: "step-num" }, cp.number), el("span", { class: "step-title" }, cp.title)));
  const prev = el("button", { class: "btn small", type: "button", "aria-label": "Previous checkpoint", onclick: () => select(index - 1) }, "‹");
  const next = el("button", { class: "btn small", type: "button", "aria-label": "Next checkpoint", onclick: () => select(index + 1) }, "›");
  const heading = el("div", { class: "step-heading" });
  const body = el("div", { class: "step-body" });

  function keyFrame(cp) {
    // This check's own annotated frame; else the phase's freeze frame; else the plain video
    // frame where that phase was detected (for checkpoints not built yet).
    const name = [`check_${cp.analyzer}.png`, cp.phase ? `${cp.phase}.png` : null].find(f => f && s.files.includes(f));
    const frame = cp.phase && s.analysis && s.analysis.phases ? s.analysis.phases[cp.phase] : undefined;
    let url = null;
    if (name) url = fileUrl(s.id, name);
    else if (frame !== undefined && s.video) url = `/api/swings/${encodeURIComponent(s.id)}/frames/${frame}.jpg?w=720`;
    if (!url) return el("div", { class: "step-frame empty-frame" }, "This moment isn't detected yet");
    return el("a", { class: "step-frame", href: url, target: "_blank", rel: "noopener", title: "Open full size" },
      el("img", { src: url, alt: `${cp.title} frame` }));
  }

  function card(cp) {
    const v = verdicts[cp.analyzer];
    if (v) return verdictCard(v);
    const missing = cp.built;
    return el("article", { class: "verdict soon" },
      el("div", { class: "verdict-head" }, el("h3", {}, cp.title),
        el("span", { class: "status-pill soon" }, missing ? "Not run" : "Coming soon")),
      el("p", { class: "verdict-summary" }, cp.description),
      missing ? el("p", { class: "small" }, "Press Re-analyze to run this check on this swing.") : null);
  }

  function select(i) {
    index = Math.max(0, Math.min(checkpoints.length - 1, i));
    const cp = checkpoints[index];
    chips.forEach((c, j) => { c.classList.toggle("current", j === index); c.setAttribute("aria-current", j === index ? "step" : "false"); });
    prev.disabled = index === 0;
    next.disabled = index === checkpoints.length - 1;
    heading.replaceChildren(el("span", { class: "subtle" }, `${cp.number} / ${checkpoints.length}`), el("strong", {}, cp.title));
    body.replaceChildren(keyFrame(cp), card(cp));
  }

  const node = el("section", { class: "panel stepper", tabindex: "-1" },
    el("div", { class: "panel-head" }, el("h2", {}, "Checkpoints"),
      el("div", { class: "legend small subtle" },
        ...["ok", "warn", "flag", "soon"].map(st => el("span", {}, el("span", { class: `dot ${st}` }), STATE_WORD[st])))),
    el("div", { class: "steps" }, chips),
    el("div", { class: "step-nav" }, prev, heading, next),
    body);
  node.addEventListener("keydown", e => {
    if (e.target instanceof HTMLInputElement || e.target instanceof HTMLVideoElement) return;
    if (e.key === "ArrowLeft") { e.preventDefault(); select(index - 1); }
    if (e.key === "ArrowRight") { e.preventDefault(); select(index + 1); }
  });
  select(index);
  return node;
}

function videoPlayer(s) {
  if (!s.files.includes("annotated.mp4")) return null;
  const video = el("video", { class: "result-video", src: fileUrl(s.id, "annotated.mp4"), controls: true, playsinline: true, preload: "metadata" });
  const speeds = [0.25, 0.5, 1].map(rate => el("button", {
    class: `btn small ${rate === 1 ? "selected" : ""}`, type: "button",
    onclick: e => {
      video.playbackRate = rate;
      for (const b of e.target.parentElement.children) b.classList.toggle("selected", b === e.target);
    },
  }, rate === 1 ? "Normal" : `${rate}×`));
  return el("section", { class: "panel" },
    el("div", { class: "panel-head" }, el("h2", {}, "Annotated swing"), el("div", { class: "actions" }, speeds)),
    video);
}

function freezeFrames(s) {
  const names = ["address", "takeaway", "top", "early_downswing", "impact"].filter(n => s.files.includes(`${n}.png`));
  if (!names.length) return null;
  return el("section", { class: "panel" },
    el("h2", {}, "Key frames"),
    el("div", { class: "freeze-row" }, names.map(n => {
      const url = fileUrl(s.id, `${n}.png`);
      return el("a", { class: "freeze", href: url, target: "_blank", rel: "noopener" },
        el("img", { src: url, alt: `${PHASE_LABELS[n]} frame`, loading: "lazy" }),
        el("span", {}, PHASE_LABELS[n]));
    })));
}

// Frame viewer for picking a phase frame by hand.
function phaseAdjuster(s, phase, startFrame, onApply, onCancel) {
  const v = s.video;
  let frame = startFrame;
  const img = el("img", { class: "adjust-frame", alt: "Video frame" });
  const label = el("span", { class: "frame-label" });
  const slider = el("input", { type: "range", class: "scrub", min: 0, max: v.frame_count - 1, value: frame, "aria-label": "Frame" });
  function show(f) {
    frame = Math.max(0, Math.min(v.frame_count - 1, f));
    slider.value = frame;
    label.textContent = `Frame ${frame} · ${(frame / v.fps).toFixed(3)}s`;
    img.src = `/api/swings/${encodeURIComponent(s.id)}/frames/${frame}.jpg?w=720`;
  }
  slider.addEventListener("input", () => show(Number(slider.value)));
  const step = n => el("button", { class: "btn small", type: "button", onclick: () => show(frame + n) },
    n === -10 ? "«" : n === -1 ? "‹" : n === 1 ? "›" : "»");
  show(frame);
  return el("div", { class: "adjuster" },
    el("p", { class: "small" }, `Scrub to the right ${PHASE_LABELS[phase].toLowerCase()} frame, then set it.`),
    el("div", { class: "adjust-stage" }, img),
    el("div", { class: "scrub-row" }, step(-10), step(-1), slider, step(1), step(10)),
    el("div", { class: "subtle small center" }, label),
    el("div", { class: "actions" },
      el("button", { class: "btn primary small", type: "button", onclick: () => onApply(frame) }, `Set as ${PHASE_LABELS[phase].toLowerCase()}`),
      el("button", { class: "btn small", type: "button", onclick: onCancel }, "Cancel")));
}

function phasesPanel(s, startAnalysis) {
  const a = s.analysis;
  const fps = (a && a.fps) || (s.video && s.video.fps) || 30;
  const manual = new Set((a && a.manual_phases) || []);
  const adjustable = ADJUSTABLE[s.view] || [];
  const body = el("div", {});

  function list() {
    body.replaceChildren(
      el("table", { class: "phases" }, el("tbody", {}, Object.entries(a.phases).map(([name, frame]) =>
        el("tr", {},
          el("th", {}, PHASE_LABELS[name] || name),
          el("td", { class: "nowrap" }, `${frame} `, el("span", { class: "subtle" }, `· ${(frame / fps).toFixed(2)}s`)),
          el("td", {}, manual.has(name) ? el("span", { class: "badge" }, name === "address" && s.view === "dtl" ? "marked" : "set by you") : ""),
          el("td", {}, adjustable.includes(name) && s.video
            ? el("button", { class: "btn small", type: "button", onclick: () => adjust(name, frame) }, "Adjust") : ""))))),
      [...manual].some(n => adjustable.includes(n))
        ? el("button", { class: "btn small", type: "button", onclick: () => startAnalysis({ reset_phases: true }) }, "Reset to automatic") : null,
      s.view === "dtl" ? el("p", { class: "subtle small" }, "Address is the frame you marked on; change it with Edit marks.") : null);
  }

  function adjust(name, frame) {
    body.replaceChildren(phaseAdjuster(s, name, frame,
      f => startAnalysis({ phases: { [name]: f } }),
      list));
  }

  list();
  // Collapsed by default: it's only needed when a detected phase is wrong.
  return el("details", { class: "panel phases-panel" },
    el("summary", {}, el("strong", {}, "Phases"), el("span", { class: "subtle small" }, " · adjust if a frame is wrong")),
    body);
}

export async function renderResults(view, s, header, isCurrent, rerender) {
  async function startAnalysis(body = {}) {
    const progress = progressBlock("Analyzing swing");
    view.replaceChildren(header(), progress.node);
    try {
      const res = await postJSON(`/api/swings/${encodeURIComponent(s.id)}/analyze`, body);
      const job = await pollJob(res.job.id, j => progress.update(j.fraction, j.message), isCurrent);
      if (job && job.state === "failed") throw new Error(job.error);
    } catch (err) {
      if (!isCurrent()) return;
      view.replaceChildren(header(), el("div", { class: "notice error" }, `Analysis failed: ${err.message}`),
        el("a", { class: "btn", href: swingUrl(s.id, "mark") }, "Check your marks"));
      return;
    }
    if (isCurrent()) await rerender();
  }

  if (s.status === "marked") {
    view.replaceChildren(header(),
      el("div", { class: "empty" },
        el("h2", {}, "Ready to analyze"),
        el("p", {}, "Tracking your body takes about a minute for a few seconds of slo-mo."),
        el("button", { class: "btn primary", type: "button", onclick: () => startAnalysis() }, "Analyze swing")));
    return;
  }

  const a = s.analysis;
  const warnings = (a && a.warnings) || [];
  const checkpoints = ((await features()).checkpoints || {})[s.view] || [];
  if (!isCurrent()) return;
  // Down-the-line: one checkpoint at a time. Other views (older face-on swings): all cards in a list.
  const checks = checkpoints.length
    ? checkpointStepper(s, checkpoints)
    : el("div", { class: "stack" }, el("section", { class: "stack-sm" }, (a.verdicts || []).map(verdictCard)), freezeFrames(s));
  const phases = phasesPanel(s, startAnalysis);
  view.replaceChildren(
    header([el("a", { class: "btn", href: fileUrl(s.id, "report.txt"), target: "_blank", rel: "noopener" }, "Report"),
      el("button", { class: "btn", type: "button", onclick: () => startAnalysis() }, "Re-analyze")]),
    ...warnings.map(w => el("div", { class: "notice" }, w)),
    el("div", { class: "results-layout" },
      el("div", { class: "stack video-col" }, videoPlayer(s)),
      el("div", { class: "stack" }, checks, phases)));
}
