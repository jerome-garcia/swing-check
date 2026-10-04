import {
  checkpointStates, el, features, fileUrl, pollJob, postJSON, progressBlock, scorecard, STATUS_WORD, swingUrl,
} from "./util.js";

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

// One compact line per measurement: status dot, name, value, and what it means underneath.
// Checks that don't supply rows (older analyses, face-on) fall back to their raw measurements.
function measurementRows(v) {
  if (v.rows && v.rows.length) return v.rows;
  return Object.entries(v.measurements || {}).filter(([k]) => !HIDDEN_MEASUREMENTS.has(k))
    .map(([k, val]) => ({ label: prettyKey(k), value: prettyValue(val), note: "", status: null }));
}

function verdictCard(v) {
  const rows = measurementRows(v);
  const showTip = v.tip && (v.status === "warn" || v.status === "flag");
  return el("article", { class: `verdict ${v.status}` },
    el("div", { class: "verdict-head" },
      el("h3", {}, v.title),
      el("span", { class: `status-pill ${v.status}` }, STATUS_WORD[v.status] || v.status)),
    el("div", { class: "verdict-label" }, v.status === "error" ? "Not measured" : v.label),
    el("p", { class: "verdict-summary" }, v.summary),
    showTip ? el("div", { class: "tip" }, el("strong", {}, "How to fix "), v.tip) : null,
    rows.length ? el("ul", { class: "rows" }, rows.map(r => el("li", {},
      r.status ? el("span", { class: `dot ${r.status}`, title: STATUS_WORD[r.status] }) : el("span", {}),
      el("span", { class: "row-label" }, r.label),
      el("span", { class: "row-value" }, r.value),
      el("span", { class: "row-note" }, r.note),
      r.good || r.fix ? el("span", { class: "row-range" },
        r.good ? el("span", {}, el("b", { class: "rng-good" }, "Good"), ` ${r.good}`) : null,
        r.fix ? el("span", {}, el("b", { class: "rng-fix" }, "Fix"), ` ${r.fix}`) : null) : null))) : null);
}

// --- Summary: the whole swing at a glance ------------------------------------
function summaryPanel(s, states, onSelect) {
  const counts = { ok: 0, warn: 0, flag: 0 };
  for (const { state } of states) if (state in counts) counts[state] += 1;
  const notMarked = states.filter(({ state }) => state === "error" || state === "missing");
  // The one thing to work on: picked at analysis time from importance tiers and how far
  // into red each fault is (swingcheck/priority.py). Older analyses without a pick: the
  // first red checkpoint in swing order, else the first yellow.
  const picked = s.analysis && s.analysis.focus;
  let focusIndex = picked ? states.findIndex(x => x.cp.analyzer === picked.checkpoint) : -1;
  if (focusIndex < 0) focusIndex = ["flag", "warn"].map(st => states.findIndex(x => x.state === st)).find(i => i >= 0);
  const focus = focusIndex !== undefined && focusIndex >= 0 ? states[focusIndex] : null;
  const focusRow = focus && picked && picked.checkpoint === focus.cp.analyzer
    ? (focus.verdict.rows || []).find(r => r.label === picked.row) : null;

  const tally = el("div", { class: "tally" },
    ...[["ok", "good"], ["warn", "to watch"], ["flag", "to fix"]].map(([st, word]) =>
      el("span", { class: `tally-item ${st}` }, el("span", { class: `dot ${st}` }), el("strong", {}, counts[st]), ` ${word}`)));

  let focusBox;
  if (focus) {
    const v = focus.verdict;
    focusBox = el("div", { class: `focus ${focus.state}` },
      el("div", { class: "focus-kicker" }, (picked ? picked.status : focus.state) === "flag" ? "Work on first" : "Worth a look"),
      el("div", { class: "focus-title" }, `${focus.cp.number}. ${focus.cp.title}: ${v.label}`),
      focusRow ? el("p", { class: "focus-row small" }, `Biggest issue: ${focusRow.label}, ${focusRow.value}`) : null,
      v.tip ? el("p", { class: "focus-tip" }, v.tip) : null,
      el("button", { class: "btn small", type: "button", onclick: () => onSelect(focusIndex) }, "See this checkpoint →"));
  } else if (counts.ok) {
    focusBox = el("div", { class: "focus ok" },
      el("div", { class: "focus-kicker" }, "Looking good"),
      el("div", { class: "focus-title" }, "Every checkpoint that was measured is in the green."));
  }

  return el("section", { class: "panel summary" },
    el("div", { class: "panel-head" }, el("h2", {}, "Swing summary"), tally),
    scorecard(states, { onSelect, labels: true }),
    focusBox || null,
    notMarked.length ? el("p", { class: "subtle small not-marked" },
      `${notMarked.map(x => x.cp.title).join(", ")} ${notMarked.length === 1 ? "isn't" : "aren't"} measured yet. `,
      el("a", { href: swingUrl(s.id, "mark") }, "Add the marks"), " to check them.") : null);
}

// --- Checkpoint stepper (down-the-line) ---------------------------------------
// The drawing language of every key frame (swingcheck/analyzers/__init__.py), as a legend.
const LEGEND = [
  ["swatch-line status", "Green / yellow / red: what was measured, colored by its result"],
  ["swatch-line dashed", "White, dashed: a target, or where you were at address"],
  ["swatch-line plane", "Magenta with grey lines: the swing plane and its on-plane zone"],
  ["swatch-line past", "Cyan: an earlier checkpoint, e.g. the clubhead at the takeaway"],
  ["mark circle", "Circle: the clubhead"],
  ["mark square", "Square: the hands"],
  ["mark ring", "Ring: the ball, a heel, or where a shaft line lands"],
];
// Shown under the legend: how to read the Good / Fix line on each measurement.
const RANGES_NOTE = "Each measurement lists its Good range (green) and its Fix range (red); anything in between is Watch (yellow). Distances are rough estimates in centimetres.";
let legendOpen = false; // kept while stepping through the checkpoints

function drawingLegend() {
  const d = el("details", { class: "legend", open: legendOpen || null },
    el("summary", {}, "How to read the drawings"),
    el("ul", {}, LEGEND.map(([cls, text]) => el("li", {}, el("span", { class: cls, "aria-hidden": "true" }), text))),
    el("p", { class: "legend-note" }, RANGES_NOTE));
  d.addEventListener("toggle", () => { legendOpen = d.open; });
  return d;
}

function checkpointStepper(s, states) {
  // Start on the first red checkpoint, else the first one with a result.
  let index = states.findIndex(x => x.state === "flag");
  if (index < 0) index = Math.max(0, states.findIndex(x => x.verdict));
  const prev = el("button", { class: "btn small", type: "button", "aria-label": "Previous checkpoint", onclick: () => select(index - 1) }, "‹");
  const next = el("button", { class: "btn small", type: "button", "aria-label": "Next checkpoint", onclick: () => select(index + 1) }, "›");
  const heading = el("div", { class: "step-heading" });
  const body = el("div", { class: "step-body" });
  const listeners = [];

  function keyFrame(cp) {
    // This check's own annotated frame; else the phase's freeze frame; else the plain video
    // frame where that phase was detected.
    const name = [`check_${cp.analyzer}.png`, cp.phase ? `${cp.phase}.png` : null].find(f => f && s.files.includes(f));
    const frame = cp.phase && s.analysis && s.analysis.phases ? s.analysis.phases[cp.phase] : undefined;
    let url = null;
    if (name) url = fileUrl(s.id, name);
    else if (frame !== undefined && s.video) url = `/api/swings/${encodeURIComponent(s.id)}/frames/${frame}.jpg?w=720`;
    if (!url) return el("div", { class: "step-frame empty-frame" }, "Mark this checkpoint to see its frame");
    return el("a", { class: "step-frame", href: url, target: "_blank", rel: "noopener", title: "Open full size" },
      el("img", { src: url, alt: `${cp.title} frame` }));
  }

  function card({ cp, verdict, state }) {
    if (verdict) return verdictCard(verdict);
    return el("article", { class: "verdict soon" },
      el("div", { class: "verdict-head" }, el("h3", {}, cp.title),
        el("span", { class: "status-pill soon" }, STATUS_WORD[state])),
      el("p", { class: "verdict-summary" }, cp.description),
      state === "missing" ? el("p", { class: "small" }, "Press Re-analyze to run this check on this swing.") : null);
  }

  function select(i) {
    index = Math.max(0, Math.min(states.length - 1, i));
    const { cp } = states[index];
    prev.disabled = index === 0;
    next.disabled = index === states.length - 1;
    heading.replaceChildren(el("span", { class: "subtle" }, `${cp.number} / ${states.length}`), el("strong", {}, cp.title));
    body.replaceChildren(el("div", { class: "step-media" }, keyFrame(cp), drawingLegend()), card(states[index]));
    listeners.forEach(fn => fn(index));
  }

  const node = el("section", { class: "panel stepper", tabindex: "-1" },
    el("div", { class: "step-nav" }, prev, heading, next),
    body);
  node.addEventListener("keydown", e => {
    if (e.target instanceof HTMLInputElement || e.target instanceof HTMLVideoElement) return;
    if (e.key === "ArrowLeft") { e.preventDefault(); select(index - 1); }
    if (e.key === "ArrowRight") { e.preventDefault(); select(index + 1); }
  });
  return { node, select, onChange: fn => listeners.push(fn), start: () => select(index) };
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
  }, rate === 1 ? "1×" : `${rate}×`));
  return el("section", { class: "panel" },
    el("div", { class: "panel-head" }, el("h2", {}, "Annotated swing"), el("div", { class: "actions segmented" }, speeds)),
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
      s.view === "dtl" ? el("p", { class: "subtle small" }, "Address and the marked checkpoints use the frames you marked; change them with Edit marks.") : null);
  }

  function adjust(name, frame) {
    body.replaceChildren(phaseAdjuster(s, name, frame,
      f => startAnalysis({ phases: { [name]: f } }),
      list));
  }

  list();
  // Collapsed by default: it's only needed when a detected phase is wrong.
  return el("details", { class: "panel phases-panel" },
    el("summary", {}, el("strong", {}, "Detected phases"), el("span", { class: "subtle small" }, " · adjust if impact or the top is off")),
    body);
}

// Warnings about the clip (low frame rate, missing frames): folded away once read.
function clipNotes(warnings) {
  if (!warnings.length) return null;
  return el("details", { class: "notice clip-notes" },
    el("summary", {}, `About this clip (${warnings.length} note${warnings.length > 1 ? "s" : ""})`),
    el("ul", {}, warnings.map(w => el("li", {}, w))));
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
        el("div", { class: "actions" },
          el("button", { class: "btn primary", type: "button", onclick: () => startAnalysis(body) }, "Try again"),
          el("a", { class: "btn", href: swingUrl(s.id, "mark") }, "Check your marks")));
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
  const reanalyze = el("button", { class: "btn primary", type: "button", onclick: () => startAnalysis() }, "Re-analyze");
  const pdf = el("a", { class: "btn", href: `/api/swings/${encodeURIComponent(s.id)}/summary.pdf`, download: "" },
    "Download summary");
  const report = { label: "Text report", href: fileUrl(s.id, "report.txt"), newTab: true };

  let main;
  if (checkpoints.length) {
    // Down-the-line: summary on top, then one checkpoint at a time.
    const states = checkpointStates(checkpoints, a.verdicts);
    const stepper = checkpointStepper(s, states);
    const summary = summaryPanel(s, states, i => {
      stepper.select(i);
      stepper.node.scrollIntoView({ behavior: "smooth", block: "start" });
    });
    // Highlight the checkpoint being shown in the summary's scorecard.
    stepper.onChange(i => summary.querySelectorAll(".score-item").forEach((b, j) => b.classList.toggle("current", i === j)));
    stepper.start();
    main = [summary, stepper.node];
  } else {
    // Other views (older face-on swings): all cards in a list.
    main = [el("section", { class: "stack-sm" }, (a.verdicts || []).map(verdictCard)), freezeFrames(s)];
  }
  view.replaceChildren(
    header([pdf, reanalyze], [report]),
    clipNotes(warnings) || "",
    el("div", { class: "results-layout" },
      el("div", { class: "stack main-col" }, ...main),
      el("div", { class: "stack side-col" }, videoPlayer(s), phasesPanel(s, startAnalysis))));
}
