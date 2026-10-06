// How to set up the camera: a setup picture per view (the camera at hip height, and a
// side view of where it goes), with the tips. The pictures are OnForm's (credited and
// linked under them). Shown on the upload page (a pop-up per camera choice) and on the
// home page before the first swing.

import { el } from "./util.js";

const SOURCE = { name: "OnForm", url: "https://onform.com/blog/how-to-video-your-golf-swing-for-better-analysis/" };

const VIEWS = {
  dtl: {
    title: "Down-the-line",
    image: "/setup/down-the-line.png",
    alt: "Down-the-line setup: the phone on a stand at hip height, behind the golfer, its view taking in the whole golfer",
    tips: ["Camera straight behind your hands, pointing at the target",
      "At about hip height, a few steps back",
      "Your whole body in frame, with room above your head for the club",
      "Upright (portrait) video; slo-mo if your phone has it"],
  },
  fo: {
    title: "Face-on",
    image: "/setup/face-on.png",
    alt: "Face-on setup: the phone on a stand at hip height, in front of the golfer, its view taking in the whole golfer",
    tips: ["Camera in front of you, square to the target line, facing your chest",
      "At about hip height, a few steps back",
      "Your whole body in frame, with room above your head for the club",
      "Upright (portrait) video; slo-mo if your phone has it"],
  },
};

// The setup picture and tips for one view (dtl or fo), as a block.
export function setupGuide(view = "dtl") {
  const v = VIEWS[view];
  return el("div", { class: "setup-guide" },
    el("figure", { class: "setup-picture" },
      el("img", { src: v.image, alt: v.alt, width: 1200, height: 676, loading: "lazy" }),
      el("figcaption", { class: "subtle small" }, "Picture: ",
        el("a", { href: SOURCE.url, target: "_blank", rel: "noopener" }, SOURCE.name))),
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
