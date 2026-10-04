import { api, checkpointStates, el, features, fileUrl, formatDate, scorecard, STATUS_TEXT, swingUrl, VIEW_NAMES } from "./util.js";

export async function renderHistory(view, isCurrent) {
  view.replaceChildren(el("p", { class: "subtle" }, "Loading swings…"));
  const [swings, feats] = await Promise.all([api("/api/swings"), features()]);
  if (!isCurrent()) return; // the user navigated away while this loaded
  const head = el("div", { class: "page-head" },
    el("div", { class: "page-title" }, el("h1", {}, "Your swings"),
      el("div", { class: "subtle small" }, swings.length ? `${swings.length} saved` : "")));

  if (!swings.length) {
    view.replaceChildren(head, el("div", { class: "empty" },
      el("h2", {}, "No swings yet"),
      el("p", {}, "Film one swing from behind (down-the-line), then upload the video to get started."),
      el("a", { class: "btn primary", href: "#/new" }, "New swing")));
    return;
  }

  const checkpointsFor = viewName => ((feats.checkpoints || {})[viewName]) || [];
  const grid = el("div", { class: "grid" }, swings.map(s => {
    const thumb = el("div", { class: "thumb" });
    // The address key frame once analyzed; before that, the clip's first frame.
    const src = s.thumbnail ? fileUrl(s.id, s.thumbnail)
      : s.status !== "uploaded" ? `/api/swings/${encodeURIComponent(s.id)}/frames/0.jpg?w=360` : null;
    if (src) thumb.style.backgroundImage = `url("${src}")`;
    else thumb.append(el("span", {}, STATUS_TEXT[s.status]));

    const checkpoints = checkpointsFor(s.view);
    let results = null;
    if (s.status === "analyzed" && checkpoints.length) {
      results = scorecard(checkpointStates(checkpoints, s.verdicts), { size: "small" });
    } else if (s.status === "analyzed") {
      results = el("div", { class: "subtle small" }, `${s.verdicts.length} checks`);
    }
    const nextStep = { converted: "Mark your swing →", marked: "Analyze →", uploaded: "Converting…" }[s.status];
    return el("a", { class: "card", href: swingUrl(s.id) },
      thumb,
      el("div", { class: "body" },
        el("div", { class: "title" }, s.name),
        el("div", { class: "meta" }, formatDate(s.created) + (s.view ? ` · ${VIEW_NAMES[s.view]}` : "")),
        results,
        nextStep ? el("span", { class: "next-step" }, nextStep) : null));
  }));
  view.replaceChildren(head, grid);
}
