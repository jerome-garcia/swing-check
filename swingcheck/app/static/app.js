// swing-check frontend: a tiny hash router over a few views.
//   #/                 history
//   #/new              upload a swing
//   #/swing/<id>       the swing (progress, results, or the next step)
//   #/swing/<id>/mark  mark points

import { renderHistory } from "./history.js";
import { renderSwing } from "./swing.js";
import { renderUpload } from "./upload.js";
import { el } from "./util.js";

// Ko-fi page for the footer's support link, e.g. "https://ko-fi.com/yourname".
// Empty hides the footer.
const KOFI_URL = "";

const view = document.getElementById("view");
if (KOFI_URL) {
  document.getElementById("support-link").href = KOFI_URL;
  document.getElementById("support").hidden = false;
}
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
