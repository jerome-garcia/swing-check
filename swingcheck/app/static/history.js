import { api, checkpointStates, dtlExample, el, expiryText, features, fileUrl, formatDate, imageUrl, plural, scorecard, STATUS_TEXT, swingUrl,
  VIEW_NAMES } from "./util.js";

// Brand band at the top of the list, like the Ko-fi cover: swing plane lines on deep green.
const HERO_ART = `<svg class="hero-art" viewBox="0 0 1160 180" preserveAspectRatio="xMaxYMid slice" aria-hidden="true">
  <g fill="none" stroke-linecap="round">
    <path d="M820 200 C 860 110, 960 40, 1180 20" stroke="#ff9f43" stroke-width="3" opacity="0.55"/>
    <path d="M860 190 C 900 120, 990 70, 1150 55" stroke="#fff" stroke-width="2" stroke-dasharray="2 10" opacity="0.4"/>
    <line x1="700" y1="210" x2="900" y2="-30" stroke="#fff" stroke-width="1.5" opacity="0.12"/>
  </g></svg>`;

function hero(count, hosted) {
  // Hosted: how many of the allowed swings are used, and how long they're kept.
  const countText = hosted
    ? `${count} of ${plural(hosted.max_swings, "swing")} · each is deleted ${plural(hosted.keep_days, "day")} after upload`
    : count ? `${count} saved` : null;
  const node = el("section", { class: "hero" },
    el("div", {},
      el("p", { class: "hero-eyebrow" }, "Nothing fancy, just geometry"),
      // A first-time visitor has no swings yet: tell them what SwingCheck does instead.
      el("h1", {}, count ? "Your swings" : "Check your golf swing"),
      el("p", {}, "Film it. Check it. Fix what matters."),
      countText ? el("p", { class: "hero-count" }, countText) : null,
      hosted && count >= hosted.max_swings
        ? el("p", { class: "hero-count" }, "That's the limit: delete one to add a new swing.") : null));
  node.insertAdjacentHTML("afterbegin", HERO_ART);
  return node;
}

// Hosted: swings belong to this browser. The private link opens them elsewhere; it's
// the owner key itself, in the URL fragment so it never reaches a server log.
function privateLink() {
  const status = el("span", { class: "subtle small", role: "status" });
  const copy = el("button", {
    class: "btn small", type: "button", onclick: async () => {
      try {
        const { key } = await api("/api/owner");
        await navigator.clipboard.writeText(`${location.origin}/#/claim/${key}`);
        status.textContent = "Copied. Keep it private: anyone with it can see your swings.";
      } catch {
        status.textContent = "Couldn't copy the link. Try again.";
      }
    },
  }, "Copy private link");
  return el("div", { class: "private-link" },
    el("p", {}, el("strong", {}, "Your swings are private to this browser. "),
      "To open them on another device, copy your private link and open it there."),
    el("div", { class: "actions" }, copy, status));
}

export async function renderHistory(view, isCurrent) {
  view.replaceChildren(el("p", { class: "subtle" }, "Loading swings…"));
  const [swings, feats] = await Promise.all([api("/api/swings"), features()]);
  if (!isCurrent()) return; // the user navigated away while this loaded
  const hosted = feats.hosted;
  const head = [hero(swings.length, hosted), hosted ? privateLink() : null];

  if (!swings.length) {
    view.replaceChildren(...head.filter(Boolean), el("div", { class: "empty" },
      el("h2", {}, "No swings yet"),
      el("p", {}, "Film one swing from behind (down-the-line), then upload the video to get started."),
      dtlExample(),
      el("a", { class: "btn primary", href: "/new" }, "New swing")));
    return;
  }

  const checkpointsFor = viewName => ((feats.checkpoints || {})[viewName]) || [];
  const grid = el("div", { class: "grid" }, swings.map(s => {
    const thumb = el("div", { class: "thumb" });
    // The address key frame once analyzed; before that, the clip's first frame.
    const src = s.thumbnail ? (s.thumbnail.endsWith(".png") ? imageUrl(s.id, s.thumbnail, s.images_version, 360) : fileUrl(s.id, s.thumbnail))
      : s.status !== "uploaded" ? `/api/swings/${encodeURIComponent(s.id)}/frames/0.jpg?w=360` : null;
    if (src) thumb.style.backgroundImage = `url("${src}")`;
    else thumb.append(el("span", {}, STATUS_TEXT[s.status]));

    const checkpoints = checkpointsFor(s.view);
    let results = null;
    if (s.status === "analyzed" && checkpoints.length) {
      results = scorecard(checkpointStates(checkpoints, s.verdicts), { size: "small" });
    } else if (s.status === "analyzed") {
      results = el("div", { class: "subtle small" }, `${s.verdicts.length} checks`);
    }
    const nextStep = { converted: "Mark your swing →", marked: "Analyze →", uploaded: "Converting…" }[s.status];
    return el("a", { class: "card", href: swingUrl(s.id) },
      thumb,
      el("div", { class: "body" },
        el("div", { class: "title" }, s.name),
        el("div", { class: "meta" }, formatDate(s.created) + (s.view ? ` · ${VIEW_NAMES[s.view]}` : "")
          + (expiryText(s) ? ` · ${expiryText(s)}` : "")),
        results,
        nextStep ? el("span", { class: "next-step" }, nextStep) : null));
  }));
  view.replaceChildren(...head.filter(Boolean), grid);
}
