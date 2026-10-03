// swing-check frontend: a tiny hash router over a few views.
//   #/                 history
//   #/new              upload a swing
//   #/swing/<id>       the swing (progress, results, or the next step)
//   #/swing/<id>/mark  mark points

import { renderHistory } from "./history.js";
import { renderSwing } from "./swing.js";
import { renderUpload } from "./upload.js";
import { el } from "./util.js";

const view = document.getElementById("view");
let navigation = 0;

async function route() {
  const current = ++navigation;
  const isCurrent = () => current === navigation;
  const hash = location.hash.replace(/^#/, "") || "/";
  const parts = hash.split("/").filter(Boolean).map(decodeURIComponent);
  try {
    if (parts.length === 0) await renderHistory(view, isCurrent);
    else if (parts[0] === "new") await renderUpload(view, isCurrent);
    else if (parts[0] === "swing" && parts[1] && parts[2] === "mark") {
      const { renderMark } = await import("./mark.js");
      await renderMark(view, parts[1], isCurrent);
    } else if (parts[0] === "swing" && parts[1]) await renderSwing(view, parts[1], isCurrent);
    else throw new Error("Page not found");
  } catch (err) {
    if (!isCurrent()) return;
    view.replaceChildren(el("div", { class: "notice error" }, `Something went wrong: ${err.message}`),
      el("a", { class: "btn", href: "#/" }, "Back to your swings"));
  }
  window.scrollTo(0, 0);
}

window.addEventListener("hashchange", route);
route();
