import { renderResults } from "./results.js";
import { api, el, expiryText, formatDate, HAND_NAMES, moreMenu, navigate, pollJob, postJSON, progressBlock, STATUS_TEXT,
  swingUrl, VIEW_NAMES } from "./util.js";

const JOB_TITLES = { convert: "Converting video", analyze: "Analyzing swing" };

// Page header: back link, name and status, the main actions as buttons, and the rest
// (always including Delete) in a "⋯" menu.
export function swingHeader(s, actions = [], menuItems = []) {
  return el("div", { class: "page-head" },
    el("div", { class: "page-title" },
      el("a", { class: "back", href: "/" }, "← Your swings"),
      el("h1", {}, s.name),
      el("div", { class: "subtle small" },
        `${formatDate(s.created)} · ${VIEW_NAMES[s.view] || "View not set"} · ${HAND_NAMES[s.handedness] || HAND_NAMES.right}`
        + ` · ${STATUS_TEXT[s.status]}`
        + (expiryText(s) ? ` · ${expiryText(s)}` : ""))),
    el("div", { class: "actions" }, ...actions, moreMenu([...menuItems, deleteItem(s)])));
}

function deleteItem(s) {
  return {
    label: "Delete swing", danger: true, onclick: async () => {
      if (!confirm(`Delete "${s.name}" and all its files? This can't be undone.`)) return;
      try {
        await api(`/api/swings/${encodeURIComponent(s.id)}`, { method: "DELETE" });
        navigate("/");
      } catch (err) { alert(err.message); }
    },
  };
}

// Show a running job's progress; re-render the swing page when it finishes.
async function showJob(view, s, job, isCurrent) {
  const progress = progressBlock(JOB_TITLES[job.kind] || "Working");
  view.replaceChildren(swingHeader(s), progress.node);
  let done;
  try {
    done = await pollJob(job.id, j => progress.update(j.fraction, j.message), isCurrent);
  } catch (err) {
    // Usually a restart: the job is gone, so show the swing as it was left.
    if (!isCurrent()) return;
    progress.node.replaceWith(el("div", { class: "notice error" }, err.message),
      el("button", { class: "btn primary", type: "button", onclick: () => renderSwing(view, s.id, isCurrent) }, "Continue"));
    return;
  }
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
  if (s.status === "uploaded" && !job) {
    // Uploaded but no conversion on record: SwingCheck restarted before it finished.
    const convertAgain = async () => {
      try {
        const res = await postJSON(`/api/swings/${encodeURIComponent(id)}/trim`, { start: s.trim_start, end: s.trim_end });
        await showJob(view, s, res.job, isCurrent);
      } catch (err) { alert(err.message); }
    };
    view.replaceChildren(swingHeader(s),
      el("div", { class: "notice" }, "This video's conversion stopped before it finished, most likely because SwingCheck restarted."),
      el("button", { class: "btn primary", type: "button", onclick: convertAgain }, "Convert again"));
    return;
  }
  if (s.status === "uploaded") {
    const reason = job.state === "failed" ? job.error : "The video hasn't been converted.";
    view.replaceChildren(swingHeader(s),
      el("div", { class: "notice error" }, `Couldn't convert this video: ${reason}`),
      el("p", { class: "subtle" }, "Delete it and try the original file from your phone, as .mov or .mp4."));
    return;
  }
  if (s.status === "converted") {
    navigate(swingUrl(id, "mark"), { replace: true });
    return;
  }
  // Results pages add Re-analyze and Report; Edit marks is always offered.
  const header = (actions = [], menu = []) => swingHeader(s, actions, [{ label: "Edit marks", href: swingUrl(id, "mark") }, ...menu]);
  await renderResults(view, s, header, isCurrent, () => renderSwing(view, id, isCurrent));
}
