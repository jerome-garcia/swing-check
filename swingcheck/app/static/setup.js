// How to set up the camera, after the reference setup pictures: for each view, the golfer
// as the camera sees them with the phone in front at hip height, and a side view of the
// whole setup (phone on its stand at hip height, its view taking in the whole golfer).
// Drawn here so they follow the app's colours in dark and light mode. Shown on the
// upload page (a pop-up per camera choice) and on the home page before the first swing.

import { el } from "./util.js";

// Figures use currentColor (the text colour); the phone, its stand and its view use the
// brand green; guide lines are muted and dashed. Ground is y = 204 in every drawing.
const LIMB = 'stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" fill="none"';

// A golfer side-on at address, facing right, centred about x = 150 (ball at the right).
const PROFILE = `
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
  <path d="M100 201 h22 M118 201 h20" stroke="currentColor" stroke-width="6" stroke-linecap="round"/>`;

// A golfer facing the viewer at address, centred on x = 130.
const FRONT = `
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
  <circle cx="137" cy="199" r="3.5" fill="currentColor"/>`;

const HIP = 112; // hip height in these drawings

// Panel 1: the golfer as the camera sees them, the phone on its stand in front of their
// hips, and a dashed line at that height. `figure` is drawn as is; `x` is the phone's x.
function cameraHeight(figure, x) {
  return `
  <line x1="6" y1="204" x2="234" y2="204" stroke="var(--border)" stroke-width="2"/>
  ${figure}
  <line x1="${x}" y1="${HIP + 20}" x2="${x}" y2="204" stroke="var(--bright)" stroke-width="3"/>
  <line x1="${x - 14}" y1="204" x2="${x + 14}" y2="204" stroke="var(--bright)" stroke-width="4" stroke-linecap="round"/>
  <rect x="${x - 14}" y="${HIP - 22}" width="28" height="42" rx="4" fill="var(--bright)"/>
  <rect x="${x - 10}" y="${HIP - 17}" width="20" height="31" rx="1.5" fill="var(--surface)"/>
  <line x1="6" y1="${HIP}" x2="234" y2="${HIP}" stroke="var(--muted)" stroke-width="1.4" stroke-dasharray="6 5"/>
  <text x="8" y="${HIP - 30}" class="dg-label">Hip height</text>`;
}

// Panel 2: the setup seen from the side. The phone (side-on, a thin bar) on its stand at
// hip height on the left; its view opens toward the golfer and takes in all of them, club
// and ball included; a dashed line runs from the phone to their hips. The golfer is drawn
// smaller (further away) by `place`, a transform that sets them on the ground at the right.
function sideView(figure, place) {
  const px = 30;
  return `
  <path d="M${px + 4} ${HIP - 14} L236 -4 L236 236 L${px + 4} ${HIP + 14} Z" fill="var(--bright)" opacity="0.1"/>
  <path d="M${px + 4} ${HIP - 14} L236 -4 M${px + 4} ${HIP + 14} L236 236" stroke="var(--bright)" stroke-width="1.4" stroke-dasharray="4 4"/>
  <line x1="${px + 4}" y1="${HIP}" x2="236" y2="${HIP}" stroke="var(--muted)" stroke-width="1.4" stroke-dasharray="6 5"/>
  <line x1="120" y1="204" x2="236" y2="204" stroke="var(--border)" stroke-width="2"/>
  <g transform="${place}">${figure}</g>
  <line x1="${px}" y1="${HIP}" x2="${px}" y2="204" stroke="var(--bright)" stroke-width="3"/>
  <line x1="${px - 14}" y1="204" x2="${px + 14}" y2="204" stroke="var(--bright)" stroke-width="4" stroke-linecap="round"/>
  <rect x="${px - 2}" y="${HIP - 18}" width="6" height="36" rx="2" fill="var(--bright)"/>
  <text x="8" y="${HIP - 30}" class="dg-label">Phone</text>`;
}

// From the side, a down-the-line golfer is seen face-on, and a face-on golfer side-on,
// facing the phone (as in the reference pictures).
const VIEWS = {
  dtl: {
    title: "Down-the-line",
    height: cameraHeight(`<g transform="translate(-30 0)">${PROFILE}</g>`, 86),
    side: sideView(FRONT, "translate(185 204) scale(0.75) translate(-130 -204)"),
    tips: ["Camera straight behind your hands, pointing at the target",
      "At about hip height, a few steps back",
      "Your whole body in frame, with room above your head for the club",
      "Upright (portrait) video; slo-mo if your phone has it"],
  },
  fo: {
    title: "Face-on",
    height: cameraHeight(`<g transform="translate(-10 0)">${FRONT}</g>`, 120),
    side: sideView(PROFILE, "translate(190 204) scale(-0.75 0.75) translate(-155 -204)"),
    tips: ["Camera in front of you, square to the target line, facing your chest",
      "At about hip height, a few steps back",
      "Your whole body in frame, with room above your head for the club",
      "Upright (portrait) video; slo-mo if your phone has it"],
  },
};

function diagram(svg, caption) {
  const fig = el("figure", { class: "dg" }, el("figcaption", {}, caption));
  fig.insertAdjacentHTML("afterbegin",
    `<svg viewBox="0 0 240 214" role="img" aria-label="${caption}">${svg}</svg>`);
  return fig;
}

// The diagrams and tips for one view (dtl or fo), as a block.
export function setupGuide(view = "dtl") {
  const v = VIEWS[view];
  return el("div", { class: "setup-guide" },
    el("div", { class: "dg-row" },
      diagram(v.height, "Camera height"),
      diagram(v.side, `${v.title}: side view`)),
    el("ul", { class: "setup-tips" }, v.tips.map(t => el("li", {}, t))));
}

// A link that opens a camera view's guide in a pop-up; `label` is its text.
export function setupLink(view, label = VIEWS[view].title) {
  const dialog = el("dialog", { class: "setup-dialog" },
    el("div", { class: "setup-dialog-head" },
      el("h2", {}, `How to set up: ${VIEWS[view].title}`),
      el("button", { class: "btn small", type: "button", onclick: () => dialog.close() }, "Close")),
    setupGuide(view));
  dialog.addEventListener("click", e => { if (e.target === dialog) dialog.close(); }); // tap outside to close
  return el("button", { class: "linkish setup-link", type: "button", onclick: () => {
    if (!dialog.isConnected) document.body.append(dialog);
    dialog.showModal();
  } }, label);
}
