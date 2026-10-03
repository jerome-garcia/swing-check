// swing-check frontend: a tiny hash router over a few views.
//   #/                 history
//   #/new              upload a swing
//   #/swing/<id>       results (or the next step if not analyzed yet)
//   #/swing/<id>/mark  mark points

const view = document.getElementById("view");

export async function api(path, options = {}) {
  const res = await fetch(path, options);
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch { /* not JSON */ }
    throw new Error(detail);
  }
  return res.status === 204 ? null : res.json();
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
const STATUS_TEXT = {
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

export function fileUrl(id, name) {
  return `/files/${encodeURIComponent(id)}/${encodeURIComponent(name)}?t=${Date.now()}`;
}

function verdictChips(verdicts) {
  return el("div", { class: "chips" },
    verdicts.map(v => el("span", { class: "chip", title: v.title },
      el("span", { class: `dot ${v.status}` }), `${v.title}: ${v.label}`)));
}

// --- History ---------------------------------------------------------------
async function renderHistory() {
  view.replaceChildren(el("p", { class: "subtle" }, "Loading swings…"));
  const swings = await api("/api/swings");
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
    const thumb = el("div", { class: "thumb" }, s.thumbnail ? "" : (s.status === "analyzed" ? "" : STATUS_TEXT[s.status]));
    if (s.thumbnail) thumb.style.backgroundImage = `url("${fileUrl(s.id, s.thumbnail)}")`;
    return el("a", { class: "card", href: `#/swing/${encodeURIComponent(s.id)}` },
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

// --- Swing (placeholder until the results page lands) ----------------------
async function renderSwing(id) {
  const s = await api(`/api/swings/${encodeURIComponent(id)}`);
  view.replaceChildren(
    el("div", { class: "page-head" },
      el("div", {}, el("h1", {}, s.name),
        el("div", { class: "subtle" }, `${formatDate(s.created)} · ${VIEW_NAMES[s.view] || "View not set"} · ${STATUS_TEXT[s.status]}`)),
      el("button", {
        class: "btn danger", onclick: async () => {
          if (!confirm(`Delete "${s.name}" and all its files? This can't be undone.`)) return;
          await api(`/api/swings/${encodeURIComponent(id)}`, { method: "DELETE" });
          location.hash = "#/";
        },
      }, "Delete")),
    s.verdicts.length ? verdictChips(s.verdicts) : el("p", { class: "subtle" }, "Not analyzed yet."));
}

// --- Router ----------------------------------------------------------------
async function route() {
  const hash = location.hash.replace(/^#/, "") || "/";
  const parts = hash.split("/").filter(Boolean).map(decodeURIComponent);
  try {
    if (parts.length === 0) await renderHistory();
    else if (parts[0] === "swing" && parts[1]) await renderSwing(parts[1]);
    else view.replaceChildren(el("div", { class: "empty" }, el("h2", {}, "Coming soon"),
      el("a", { class: "btn", href: "#/" }, "Back to your swings")));
  } catch (err) {
    view.replaceChildren(el("div", { class: "notice error" }, `Something went wrong: ${err.message}`),
      el("a", { class: "btn", href: "#/" }, "Back to your swings"));
  }
  window.scrollTo(0, 0);
}

window.addEventListener("hashchange", route);
route();
