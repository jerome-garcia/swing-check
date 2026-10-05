// Shared helpers for the SwingCheck frontend.

const OFFLINE = "Can't reach the SwingCheck app. Is it still running? If you closed or restarted it, start it again and try once more.";

export async function api(path, options = {}) {
  let res;
  try {
    res = await fetch(path, options);
  } catch {
    // fetch() only throws when there's no answer at all: the app isn't running.
    const err = new Error(OFFLINE);
    err.offline = true;
    throw err;
  }
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch { /* not JSON */ }
    const err = new Error(detail);
    err.status = res.status;
    throw err;
  }
  return res.status === 204 ? null : res.json();
}

export function postJSON(path, body) {
  return api(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
}

export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") node.className = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else if (k === "style" && typeof v === "object") Object.assign(node.style, v);
    else node.setAttribute(k, v === true ? "" : v);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

export const VIEW_NAMES = { dtl: "Down-the-line", fo: "Face-on" };
export const HAND_NAMES = { right: "Right-handed", left: "Left-handed" };

// Which features the server has switched on (e.g. face-on is held for a future release).
let featuresPromise = null;
export function features() {
  featuresPromise = featuresPromise || api("/api/features");
  return featuresPromise;
}

export const STATUS_TEXT = {
  uploaded: "Converting",
  converted: "Needs marking",
  marked: "Ready to analyze",
  analyzed: "Analyzed",
};

export function formatDate(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, { month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit" });
}

// A key-frame PNG as shown on the page: a small JPEG copy (the server makes it; see
// web_image), cached by the browser and checked for changes on each visit.
export function imageUrl(id, png, width = 720) {
  return `${fileUrl(id, png.replace(/\.png$/, ".jpg"), false)}?w=${width}`;
}

export function fileUrl(id, name, bust = true) {
  const url = `/files/${encodeURIComponent(id)}/${encodeURIComponent(name)}`;
  return bust ? `${url}?t=${Date.now()}` : url;
}

// Hosted: "Deletes on Oct 8" for a swing that expires (none when run locally).
export function expiryText(s) {
  if (!s.expires) return null;
  const d = new Date(s.expires);
  return Number.isNaN(d.getTime()) ? null : `Deletes on ${d.toLocaleDateString(undefined, { month: "short", day: "numeric" })}`;
}

// "a", "a and b", "a, b, and c" (with the Oxford comma, as all SwingCheck text).
export function listText(items, conjunction = "and") {
  if (items.length <= 2) return items.join(` ${conjunction} `);
  return `${items.slice(0, -1).join(", ")}, ${conjunction} ${items[items.length - 1]}`;
}

export function plural(n, word) {
  return `${n} ${word}${n === 1 ? "" : "s"}`;
}

// Go to one of the app's pages without reloading (app.js routes on popstate).
// replace: swap the current history entry instead of adding one.
export function navigate(url, { replace = false } = {}) {
  history[replace ? "replaceState" : "pushState"](null, "", url);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

export function swingUrl(id, sub = "") {
  return `/swing/${encodeURIComponent(id)}${sub ? "/" + sub : ""}`;
}

export function verdictChips(verdicts) {
  return el("div", { class: "chips" },
    verdicts.map(v => el("span", { class: "chip", title: v.title },
      el("span", { class: `dot ${v.status}` }), `${v.title}: ${v.label}`)));
}

export const STATUS_WORD = { ok: "Good", warn: "Watch", flag: "Fix", error: "Not marked", missing: "Not run", soon: "Coming soon" };

// Status of each checkpoint, in swing order: "ok" | "warn" | "flag" | "error" (no data,
// usually not marked) | "missing" (not run on this swing) | "soon" (not built).
export function checkpointStates(checkpoints, verdicts) {
  const byName = Object.fromEntries((verdicts || []).map(v => [v.name, v]));
  return checkpoints.map(cp => {
    const v = byName[cp.analyzer];
    return { cp, verdict: v || null, state: !cp.built ? "soon" : v ? v.status : "missing" };
  });
}

// Row of numbered status dots, one per checkpoint. `onSelect(i)` makes them buttons;
// `labels` adds each checkpoint's name under its dot.
export function scorecard(states, { onSelect = null, labels = false, size = "" } = {}) {
  return el("div", { class: `scorecard ${labels ? "labeled" : ""} ${size}` }, states.map(({ cp, state, verdict }, i) => {
    const title = `${cp.number}. ${cp.title}: ${verdict && verdict.status !== "error" ? verdict.label : STATUS_WORD[state]}`;
    const inner = [el("span", { class: `score-dot ${state}` }, cp.number),
      labels ? el("span", { class: "score-label" }, cp.title) : null];
    return onSelect
      ? el("button", { type: "button", class: "score-item", title, "data-index": i, onclick: () => onSelect(i) }, ...inner)
      : el("span", { class: "score-item", title }, ...inner);
  }));
}

// "⋯" menu of secondary actions. Items: {label, href?, onclick?, danger?}.
export function moreMenu(items) {
  const menu = el("details", { class: "menu" },
    el("summary", { class: "btn", "aria-label": "More actions", title: "More actions" }, "⋯"),
    el("div", { class: "menu-list", role: "menu" }, items.filter(Boolean).map(it => it.href
      ? el("a", { class: `menu-item ${it.danger ? "danger" : ""}`, role: "menuitem", href: it.href,
        target: it.newTab ? "_blank" : null, rel: it.newTab ? "noopener" : null }, it.label)
      : el("button", { type: "button", class: `menu-item ${it.danger ? "danger" : ""}`, role: "menuitem",
        onclick: e => { menu.open = false; it.onclick(e); } }, it.label))));
  // Close when clicking anywhere else.
  document.addEventListener("click", e => { if (menu.open && !menu.contains(e.target)) menu.open = false; });
  return menu;
}

// Poll a job until it finishes; onUpdate(job) is called on every poll.
// Resolves with the finished job; stops (resolving null) if `isCurrent()` turns false,
// e.g. after the user navigated away.
// If the app stops answering, it keeps trying for a while (it may be busy or restarting);
// jobs live in the app's memory, so after a restart the job is gone and that's reported.
export async function pollJob(jobId, onUpdate, isCurrent = () => true) {
  let offlineSince = null;
  while (isCurrent()) {
    let job;
    try {
      job = await api(`/api/jobs/${jobId}`);
      offlineSince = null;
    } catch (err) {
      if (err.status === 404) {
        throw new Error("SwingCheck restarted while this was running, so it stopped. Start it again from here.");
      }
      if (!err.offline) throw err;
      offlineSince ??= Date.now();
      if (Date.now() - offlineSince > 15000) throw err;
      onUpdate({ fraction: null, message: "Lost contact with the app, retrying…" });
      await new Promise(r => setTimeout(r, 1000));
      continue;
    }
    onUpdate(job);
    if (job.state === "done" || job.state === "failed") return job;
    await new Promise(r => setTimeout(r, 500));
  }
  return null;
}

export function progressBlock(title) {
  const bar = el("div", { class: "bar-fill" });
  const message = el("div", { class: "subtle" }, "Starting…");
  const node = el("div", { class: "progress-card" },
    el("h2", {}, title), el("div", { class: "bar" }, bar), message);
  return {
    node,
    update(fraction, text) {
      const known = fraction !== null && fraction !== undefined;
      bar.classList.toggle("indeterminate", !known);
      bar.style.width = known ? `${Math.round(fraction * 100)}%` : "";
      if (text) message.textContent = known && !text.includes("%") ? `${text} · ${Math.round(fraction * 100)}%` : text;
    },
  };
}
