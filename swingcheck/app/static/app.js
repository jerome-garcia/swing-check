// SwingCheck frontend: a tiny router over a few views, on clean addresses.
//   /                  history
//   /new               upload a swing
//   /swing/<id>        the swing (progress, results, or the next step)
//   /swing/<id>/mark   mark points
//   /terms, /privacy   terms of use and privacy notice
//   /feedback          send feedback
//   /#/claim/<key>     hosted: a private link, opening that owner's swings here. It stays
//                      after the "#" on purpose: browsers never send that part to a server,
//                      so the key never reaches a log.
// Links to these pages switch views in place (no reload); the server answers each address
// with the app too, for refreshes and links from outside. Old #/ links still work.

import { renderFeedback } from "./feedback.js";
import { renderHistory } from "./history.js";
import { renderLegal } from "./legal.js";
import { renderSwing } from "./swing.js";
import { renderUpload } from "./upload.js";
import { el, features, navigate, postJSON } from "./util.js";

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
// Dark by default; the footer switch flips to light and back, remembered in this browser.
const themeToggle = document.getElementById("theme-toggle");
function showTheme() {
  const light = document.documentElement.dataset.theme === "light";
  themeToggle.textContent = light ? "Dark mode" : "Light mode";
}
themeToggle.addEventListener("click", () => {
  const light = document.documentElement.dataset.theme !== "light";
  if (light) document.documentElement.dataset.theme = "light";
  else delete document.documentElement.dataset.theme;
  try { localStorage.setItem("swingcheck.theme", light ? "light" : "dark"); } catch { /* just not remembered */ }
  showTheme();
});
showTheme();
let navigation = 0;

async function route() {
  const current = ++navigation;
  const isCurrent = () => current === navigation;
  try {
    // A #/ address: the private link, or an old link from before clean addresses.
    if (location.hash.startsWith("#/")) {
      const old = location.hash.slice(1);
      const [, first, key] = old.split("/");
      // Take a private key out of the address bar and history first, then claim it.
      history.replaceState(null, "", first === "claim" ? "/" : old);
      if (first === "claim" && key) await postJSON("/api/owner/claim", { key: decodeURIComponent(key) });
    }
    const parts = location.pathname.split("/").filter(Boolean).map(decodeURIComponent);
    if (parts[0] === "terms" || parts[0] === "privacy") await renderLegal(view, parts[0], isCurrent);
    else if (parts[0] === "feedback") renderFeedback(view);
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
      el("a", { class: "btn", href: "/" }, "Back to your swings"));
  }
  window.scrollTo(0, 0);
}

// Links to the app's own pages switch views in place. Left alone: other sites, new tabs
// (target, or Ctrl/Cmd/Shift/middle click), downloads, and files and the API.
document.addEventListener("click", e => {
  const a = e.target.closest && e.target.closest("a[href]");
  if (!a || e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
  if ((a.target && a.target !== "_self") || a.hasAttribute("download") || a.origin !== location.origin) return;
  if (/^\/(api|files)\//.test(a.pathname) || /\.[a-z0-9]+$/i.test(a.pathname)) return;
  e.preventDefault();
  if (a.pathname + a.search !== location.pathname + location.search || location.hash) navigate(a.pathname + a.search);
});
window.addEventListener("popstate", route);
// A #/ address typed or pasted into a tab already on this site (e.g. the private link on
// the home page) changes only the fragment: no reload, so route it here.
window.addEventListener("hashchange", route);
route();
