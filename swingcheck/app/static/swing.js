import { renderResults } from "./results.js";
import { api, el, formatDate, moreMenu, pollJob, progressBlock, putJSON, STATUS_TEXT, swingUrl, VIEW_NAMES } from "./util.js";

const JOB_TITLES = { convert: "Converting video", analyze: "Analyzing swing" };

// Page header: back link, name and status, the main actions as buttons, and the rest
// (always including Delete) in a "⋯" menu.
export function swingHeader(s, actions = [], menuItems = []) {
  return el("div", { class: "page-head" },
    el("div", { class: "page-title" },
      el("a", { class: "back", href: "#/" }, "← Your swings"),
      el("h1", {}, s.name),
      el("div", { class: "subtle small" },
        `${formatDate(s.created)} · ${VIEW_NAMES[s.view] || "View not set"} · ${STATUS_TEXT[s.status]}`)),
    el("div", { class: "actions" }, ...actions, moreMenu([...menuItems, deleteItem(s)])));
}

function deleteItem(s) {
  return {
    label: "Delete swing", danger: true, onclick: async () => {
      if (!confirm(`Delete "${s.name}" and all its files? This can't be undone.`)) return;
      try {
        await api(`/api/swings/${encodeURIComponent(s.id)}`, { method: "DELETE" });
        location.hash = "#/";
      } catch (err) { alert(err.message); }
    },
  };
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
  // Results pages add Re-analyze and Report; Edit marks is always offered, and a down-the-line
  // swing can be the marking reference (its frames show beside each marking step).
  const reference = await api("/api/reference").catch(() => ({ id: null }));
  if (!isCurrent()) return;
  const isReference = reference.id === id;
  const referenceItem = s.view === "dtl" ? {
    label: isReference ? "Stop using as marking reference" : "Use as marking reference",
    onclick: async () => {
      try {
        await putJSON("/api/reference", { id: isReference ? null : id });
        await renderSwing(view, id, isCurrent);
      } catch (err) { alert(err.message); }
    },
  } : null;
  const header = (actions = [], menu = []) => swingHeader(s, actions,
    [{ label: "Edit marks", href: swingUrl(id, "mark") }, ...(referenceItem ? [referenceItem] : []), ...menu]);
  await renderResults(view, s, header, isCurrent, () => renderSwing(view, id, isCurrent));
}
