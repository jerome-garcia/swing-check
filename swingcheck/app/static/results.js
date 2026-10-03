import { el, fileUrl, pollJob, postJSON, progressBlock, swingUrl } from "./util.js";

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

function verdictCard(v) {
  const rows = Object.entries(v.measurements || {}).filter(([k]) => !HIDDEN_MEASUREMENTS.has(k));
  return el("article", { class: `verdict ${v.status}` },
    el("div", { class: "verdict-head" },
      el("h3", {}, v.title),
      el("span", { class: `status-pill ${v.status}` }, STATUS_WORD[v.status] || v.status)),
    el("div", { class: "verdict-label" }, v.label),
    el("p", { class: "verdict-summary" }, v.summary),
    rows.length ? el("table", { class: "measurements" },
      el("tbody", {}, rows.map(([k, val]) => el("tr", {}, el("th", {}, prettyKey(k)), el("td", {}, prettyValue(val)))))) : null,
    v.measurements && v.measurements.units ? el("div", { class: "subtle small" }, v.measurements.units) : null);
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
  return el("section", { class: "panel" }, el("h2", {}, "Phases"), body);
}

export function renderResults(view, s, header, isCurrent, rerender) {
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
  view.replaceChildren(
    header([el("a", { class: "btn", href: fileUrl(s.id, "report.txt"), target: "_blank", rel: "noopener" }, "Report"),
      el("button", { class: "btn", type: "button", onclick: () => startAnalysis() }, "Re-analyze")]),
    ...warnings.map(w => el("div", { class: "notice" }, w)),
    el("div", { class: "results-layout" },
      el("div", { class: "stack" }, videoPlayer(s), freezeFrames(s)),
      el("div", { class: "stack" },
        el("section", { class: "stack-sm" }, (a.verdicts || []).map(verdictCard)),
        phasesPanel(s, startAnalysis))));
}
