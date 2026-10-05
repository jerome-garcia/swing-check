// SwingCheck frontend: a tiny hash router over a few views.
//   #/                 history
//   #/new              upload a swing
//   #/swing/<id>       the swing (progress, results, or the next step)
//   #/swing/<id>/mark  mark points
//   #/claim/<key>      hosted: a private link, opening that owner's swings here
//   #/terms, #/privacy terms of use and privacy notice

import { renderHistory } from "./history.js";
import { renderLegal } from "./legal.js";
import { renderSwing } from "./swing.js";
import { renderUpload } from "./upload.js";
import { el, features, postJSON } from "./util.js";

// Ko-fi page for the footer's support link, e.g. "https://ko-fi.com/yourname".
// Empty hides the footer.
const KOFI_URL = "https://ko-fi.com/jeromegarcia";

const view = document.getElementById("view");
if (KOFI_URL) {
  document.getElementById("support-link").href = KOFI_URL;
  document.getElementById("support").hidden = false;
}
// The running version under the name, e.g. "v0.1.0" for v0.1.0-alpha (the badge already says Alpha).
features().then(f => {
  const version = document.getElementById("app-version");
  version.textContent = (f.version || "").replace("-alpha", "");
  version.title = `SwingCheck ${f.version}`;
  version.hidden = !f.version;
}).catch(() => { /* the header just goes without it */ });
let navigation = 0;

async function route() {
  const current = ++navigation;
  const isCurrent = () => current === navigation;
  const hash = location.hash.replace(/^#/, "") || "/";
  const parts = hash.split("/").filter(Boolean).map(decodeURIComponent);
  try {
    if (parts[0] === "claim" && parts[1]) {
      // Take the key out of the address bar and history first, then claim it.
      history.replaceState(null, "", "#/");
      await postJSON("/api/owner/claim", { key: parts[1] });
      await renderHistory(view, isCurrent);
    } else if (parts[0] === "terms" || parts[0] === "privacy") await renderLegal(view, parts[0], isCurrent);
    else if (parts.length === 0) await renderHistory(view, isCurrent);
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
