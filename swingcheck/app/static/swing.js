import { api, el, formatDate, pollJob, progressBlock, STATUS_TEXT, swingUrl, verdictChips, VIEW_NAMES } from "./util.js";

const JOB_TITLES = { convert: "Converting video", analyze: "Analyzing swing" };

export function swingHeader(s, extraActions = []) {
  return el("div", { class: "page-head" },
    el("div", {},
      el("a", { class: "back", href: "#/" }, "← Your swings"),
      el("h1", {}, s.name),
      el("div", { class: "subtle" },
        `${formatDate(s.created)} · ${VIEW_NAMES[s.view] || "View not set"} · ${STATUS_TEXT[s.status]}`)),
    el("div", { class: "actions" }, ...extraActions, deleteButton(s)));
}

function deleteButton(s) {
  return el("button", {
    class: "btn danger", onclick: async () => {
      if (!confirm(`Delete "${s.name}" and all its files? This can't be undone.`)) return;
      try {
        await api(`/api/swings/${encodeURIComponent(s.id)}`, { method: "DELETE" });
        location.hash = "#/";
      } catch (err) { alert(err.message); }
    },
  }, "Delete");
}

// Show a running job's progress; re-render the swing page when it finishes.
async function showJob(view, s, job, isCurrent) {
  const progress = progressBlock(JOB_TITLES[job.kind] || "Working");
  view.replaceChildren(swingHeader(s), progress.node);
  const done = await pollJob(job.id, j => progress.update(j.fraction, j.message), isCurrent);
  if (done && isCurrent()) await renderSwing(view, s.id, isCurrent);
}

export async function renderSwing(view, id, isCurrent) {
  const s = await api(`/api/swings/${encodeURIComponent(id)}`);
  if (!isCurrent()) return;
  const job = s.job;

  if (job && (job.state === "queued" || job.state === "running")) {
    await showJob(view, s, job, isCurrent);
    return;
  }
  if (s.status === "uploaded") {
    const reason = job && job.state === "failed" ? job.error : "The video hasn't been converted.";
    view.replaceChildren(swingHeader(s),
      el("div", { class: "notice error" }, `Couldn't convert this video: ${reason}`),
      el("p", { class: "subtle" }, "Delete it and try the original file from your phone, as .mov or .mp4."));
    return;
  }
  if (s.status === "converted") {
    location.replace(swingUrl(id, "mark"));
    return;
  }
  if (s.status === "marked") {
    view.replaceChildren(swingHeader(s, [el("a", { class: "btn", href: swingUrl(id, "mark") }, "Edit marks")]),
      el("div", { class: "empty" }, el("h2", {}, "Ready to analyze"),
        el("p", {}, "Analysis from the app is coming in the next step.")));
    return;
  }
  view.replaceChildren(swingHeader(s, [el("a", { class: "btn", href: swingUrl(id, "mark") }, "Edit marks")]),
    verdictChips(s.verdicts));
}
