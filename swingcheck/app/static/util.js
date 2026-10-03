// Shared helpers for the swing-check frontend.

export async function api(path, options = {}) {
  const res = await fetch(path, options);
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch { /* not JSON */ }
    throw new Error(detail);
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
export async function pollJob(jobId, onUpdate, isCurrent = () => true) {
  while (isCurrent()) {
    const job = await api(`/api/jobs/${jobId}`);
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
