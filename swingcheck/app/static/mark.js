import { api, el } from "./util.js";
import { swingHeader } from "./swing.js";

export async function renderMark(view, id, isCurrent) {
  const s = await api(`/api/swings/${encodeURIComponent(id)}`);
  if (!isCurrent()) return;
  view.replaceChildren(swingHeader(s),
    el("div", { class: "empty" }, el("h2", {}, "Marking"), el("p", {}, "The marking screen is coming in the next step.")));
}
