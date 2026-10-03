import { api, el, fileUrl, formatDate, STATUS_TEXT, swingUrl, verdictChips, VIEW_NAMES } from "./util.js";

export async function renderHistory(view, isCurrent) {
  view.replaceChildren(el("p", { class: "subtle" }, "Loading swings…"));
  const swings = await api("/api/swings");
  if (!isCurrent()) return; // the user navigated away while this loaded
  const head = el("div", { class: "page-head" },
    el("div", {}, el("h1", {}, "Your swings"),
      el("div", { class: "subtle" }, swings.length ? `${swings.length} saved` : "")));

  if (!swings.length) {
    view.replaceChildren(head, el("div", { class: "empty" },
      el("h2", {}, "No swings yet"),
      el("p", {}, "Upload a video of one swing to get started."),
      el("a", { class: "btn primary", href: "#/new" }, "New swing")));
    return;
  }

  const grid = el("div", { class: "grid" }, swings.map(s => {
    const thumb = el("div", { class: "thumb" }, s.thumbnail ? "" : STATUS_TEXT[s.status]);
    if (s.thumbnail) thumb.style.backgroundImage = `url("${fileUrl(s.id, s.thumbnail)}")`;
    return el("a", { class: "card", href: swingUrl(s.id) },
      thumb,
      el("div", { class: "body" },
        el("div", { class: "title" }, s.name),
        el("div", { class: "meta" },
          el("span", {}, formatDate(s.created)),
          s.view ? el("span", { class: "badge" }, VIEW_NAMES[s.view]) : null,
          s.status !== "analyzed" ? el("span", { class: "badge" }, STATUS_TEXT[s.status]) : null),
        s.verdicts.length ? verdictChips(s.verdicts) : null));
  }));
  view.replaceChildren(head, grid);
}
