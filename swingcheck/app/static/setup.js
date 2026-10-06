// How to set up the camera: two simple diagrams per view (what the camera sees, with
// the phone at hip height; and from above, where the phone goes), drawn here so they
// follow the app's colours in dark and light mode. Shown on the upload page (in a
// pop-up per camera choice) and on the home page before the first swing.

import { el } from "./util.js";

// Shared pieces. Figures use currentColor (the text colour); the phone, its stand and
// its view cone use the brand green; guide lines are muted and dashed.
const PHONE = (x, y) =>
  `<rect x="${x - 7}" y="${y - 12}" width="14" height="24" rx="3" fill="var(--bright)"/>`
  + `<rect x="${x - 4.5}" y="${y - 8.5}" width="9" height="16" rx="1" fill="var(--surface)"/>`;
const STAND = (x, top, ground) =>
  `<line x1="${x}" y1="${top}" x2="${x}" y2="${ground}" stroke="var(--bright)" stroke-width="2.5"/>`
  + `<line x1="${x - 12}" y1="${ground}" x2="${x + 12}" y2="${ground}" stroke="var(--bright)" stroke-width="3" stroke-linecap="round"/>`;
const HIP_LINE = (y, label) =>
  `<line x1="6" y1="${y}" x2="214" y2="${y}" stroke="var(--muted)" stroke-width="1.2" stroke-dasharray="5 5"/>`
  + `<text x="8" y="${y - 24}" class="dg-label">${label}</text>`;
const LIMB = 'stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" fill="none"';
const GROUND = '<line x1="6" y1="204" x2="214" y2="204" stroke="var(--border)" stroke-width="2"/>';

// Down-the-line, as the camera sees it: the golfer side-on at address, facing right.
const DTL_SEEN = `
  ${GROUND}
  <g ${LIMB}>
    <polyline points="112,118 120,158 110,198" stroke-width="13"/>
    <polyline points="108,118 128,156 126,198" stroke-width="13"/>
    <line x1="110" y1="116" x2="146" y2="62" stroke-width="26"/>
    <line x1="146" y1="68" x2="156" y2="124" stroke-width="10"/>
    <line x1="156" y1="124" x2="196" y2="196" stroke-width="3"/>
  </g>
  <circle cx="160" cy="46" r="12" fill="currentColor"/>
  <rect x="190" y="193" width="12" height="6" rx="2" fill="currentColor"/>
  <circle cx="207" cy="199" r="3.5" fill="currentColor"/>
  <path d="M100 201 h22 M118 201 h20" stroke="currentColor" stroke-width="6" stroke-linecap="round"/>
  ${STAND(38, 120, 204)}${PHONE(38, 112)}
  ${HIP_LINE(112, "Hip height")}`;

// Down-the-line from above: target at the top; the golfer (a right-hander) faces right,
// the ball in front; the phone straight behind the hands, looking up the target line.
const DTL_ABOVE = `
  <path d="M132 10 l-6 10 h12 z" fill="var(--muted)"/>
  <text x="142" y="20" class="dg-label">Target</text>
  <line x1="132" y1="22" x2="132" y2="214" stroke="var(--muted)" stroke-width="1.2" stroke-dasharray="5 5"/>
  <path d="M112 196 L64 40 L160 40 Z" fill="var(--bright)" opacity="0.13"/>
  <path d="M112 196 L64 40 M112 196 L160 40" stroke="var(--bright)" stroke-width="1.2" stroke-dasharray="3 4"/>
  <ellipse cx="86" cy="108" rx="11" ry="27" fill="currentColor"/>
  <circle cx="90" cy="108" r="8" fill="var(--surface)" stroke="currentColor" stroke-width="3"/>
  <line x1="94" y1="108" x2="112" y2="108" stroke="currentColor" stroke-width="7" stroke-linecap="round"/>
  <text x="86" y="150" text-anchor="middle" class="dg-label">You</text>
  <circle cx="132" cy="108" r="4" fill="currentColor"/>
  <text x="140" y="112" class="dg-label">Ball</text>
  ${PHONE(112, 200)}
  <text x="124" y="204" class="dg-label">Phone</text>`;

// Face-on, as the camera sees it: the golfer facing the camera at address.
const FO_SEEN = `
  ${GROUND}
  <g ${LIMB}>
    <polyline points="118,120 108,160 100,198" stroke-width="13"/>
    <polyline points="142,120 152,160 160,198" stroke-width="13"/>
    <line x1="130" y1="116" x2="130" y2="70" stroke-width="28"/>
    <polyline points="112,70 120,100 129,128" stroke-width="8"/>
    <polyline points="148,70 140,100 131,128" stroke-width="8"/>
    <line x1="130" y1="128" x2="126" y2="198" stroke-width="3"/>
  </g>
  <circle cx="130" cy="42" r="13" fill="currentColor"/>
  <rect x="118" y="195" width="12" height="6" rx="2" fill="currentColor"/>
  <circle cx="137" cy="199" r="3.5" fill="currentColor"/>
  ${STAND(38, 120, 204)}${PHONE(38, 112)}
  ${HIP_LINE(112, "Hip height")}`;

// Face-on from above: target at the top; the phone in front of the golfer, square to
// the target line, looking at their chest.
const FO_ABOVE = `
  <path d="M132 10 l-6 10 h12 z" fill="var(--muted)"/>
  <text x="142" y="20" class="dg-label">Target</text>
  <line x1="132" y1="22" x2="132" y2="214" stroke="var(--muted)" stroke-width="1.2" stroke-dasharray="5 5"/>
  <path d="M196 108 L60 60 L60 156 Z" fill="var(--bright)" opacity="0.13"/>
  <path d="M196 108 L60 60 M196 108 L60 156" stroke="var(--bright)" stroke-width="1.2" stroke-dasharray="3 4"/>
  <ellipse cx="86" cy="108" rx="11" ry="27" fill="currentColor"/>
  <circle cx="90" cy="108" r="8" fill="var(--surface)" stroke="currentColor" stroke-width="3"/>
  <line x1="94" y1="108" x2="112" y2="108" stroke="currentColor" stroke-width="7" stroke-linecap="round"/>
  <text x="86" y="150" text-anchor="middle" class="dg-label">You</text>
  <circle cx="132" cy="108" r="4" fill="currentColor"/>
  <text x="128" y="126" text-anchor="end" class="dg-label">Ball</text>
  <g transform="rotate(90 200 108)">${PHONE(200, 108)}</g>
  <text x="204" y="136" text-anchor="end" class="dg-label">Phone</text>`;

const VIEWS = {
  dtl: {
    title: "Down-the-line",
    seen: DTL_SEEN, above: DTL_ABOVE,
    tips: ["Camera straight behind your hands, pointing at the target",
      "At about hip height, a few steps back",
      "Your whole body in frame, with room above your head for the club",
      "Upright (portrait) video; slo-mo if your phone has it"],
  },
  fo: {
    title: "Face-on",
    seen: FO_SEEN, above: FO_ABOVE,
    tips: ["Camera in front of you, square to the target line, facing your chest",
      "At about hip height, a few steps back",
      "Your whole body in frame, with room above your head for the club",
      "Upright (portrait) video; slo-mo if your phone has it"],
  },
};

function diagram(svg, caption) {
  const fig = el("figure", { class: "dg" }, el("figcaption", {}, caption));
  fig.insertAdjacentHTML("afterbegin",
    `<svg viewBox="0 0 220 214" role="img" aria-label="${caption}">${svg}</svg>`);
  return fig;
}

// The diagrams and tips for one view (dtl or fo), as a block.
export function setupGuide(view = "dtl") {
  const v = VIEWS[view];
  return el("div", { class: "setup-guide" },
    el("div", { class: "dg-row" },
      diagram(v.seen, "What the camera sees"),
      diagram(v.above, "From above")),
    el("ul", { class: "setup-tips" }, v.tips.map(t => el("li", {}, t))),
    view === "dtl" ? el("figure", { class: "dtl-example" },
      el("img", { src: "/reference/address.jpg", alt: "A golfer filmed down-the-line, at address", width: 480, height: 853,
        loading: "lazy" }),
      el("figcaption", {}, el("strong", {}, "What your video should look like"),
        el("span", { class: "subtle small" }, "Rory McIlroy at address, filmed down-the-line"))) : null);
}

// A link that opens a camera view's guide in a pop-up; `label` is its text.
export function setupLink(view, label = VIEWS[view].title) {
  const dialog = el("dialog", { class: "setup-dialog" },
    el("div", { class: "setup-dialog-head" },
      el("h2", {}, `How to set up: ${VIEWS[view].title}`),
      el("button", { class: "btn small", type: "button", onclick: () => dialog.close() }, "Close")),
    setupGuide(view));
  dialog.addEventListener("click", e => { if (e.target === dialog) dialog.close(); }); // tap outside to close
  const link = el("button", { class: "linkish setup-link", type: "button", onclick: () => {
    if (!dialog.isConnected) document.body.append(dialog);
    dialog.showModal();
  } }, label);
  return link;
}
