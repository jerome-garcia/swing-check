// Shared helpers for the swing-check frontend.

const OFFLINE = "Can't reach the swing-check app. Is it still running? If you closed or restarted it, start it again and try once more.";

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

export function fileUrl(id, name, bust = true) {
  const url = `/files/${encodeURIComponent(id)}/${encodeURIComponent(name)}`;
  return bust ? `${url}?t=${Date.now()}` : url;
}

export function swingUrl(id, sub = "") {
  return `#/swing/${encodeURIComponent(id)}${sub ? "/" + sub : ""}`;
}

export function verdictChips(verdicts) {
  return el("div", { class: "chips" },
    verdicts.map(v => el("span", { class: "chip", title: v.title },
      el("span", { class: `dot ${v.status}` }), `${v.title}: ${v.label}`)));
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
        throw new Error("The app was restarted while this was running, so it stopped. Start it again from here.");
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
