import { TERMS_VERSION } from "./legal.js";
import { api, el, features, HAND_NAMES, listText, navigate, plural, progressBlock, swingUrl } from "./util.js";

const HAND_KEY = "swingcheck.handedness"; // the last choice, so it's preset next time

function rememberedHand() {
  try { return localStorage.getItem(HAND_KEY) === "left" ? "left" : "right"; } catch { return "right"; }
}

function rememberHand(hand) {
  try { localStorage.setItem(HAND_KEY, hand); } catch { /* private window: just not remembered */ }
}

// Upload with XMLHttpRequest: fetch() can't report upload progress.
function uploadWithProgress(file, viewChoice, hand, agreed, onProgress) {
  return new Promise((resolve, reject) => {
    const form = new FormData();
    form.append("file", file);
    form.append("view", viewChoice);
    form.append("handedness", hand);
    if (agreed) form.append("agreed_terms", TERMS_VERSION);
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/swings");
    xhr.upload.onprogress = e => { if (e.lengthComputable) onProgress(e.loaded / e.total); };
    xhr.onload = () => {
      let body = null;
      try { body = JSON.parse(xhr.responseText); } catch { /* ignore */ }
      if (xhr.status >= 200 && xhr.status < 300) resolve(body);
      else reject(new Error((body && body.detail) || `Upload failed (${xhr.status})`));
    };
    xhr.onerror = () => reject(new Error("Upload failed: the connection was interrupted."));
    xhr.send(form);
  });
}

export async function renderUpload(view, isCurrent) {
  const { face_on: faceOn, hosted } = await features();
  const used = hosted ? (await api("/api/owner")).swings : 0;
  if (!isCurrent()) return;
  const title = el("div", { class: "page-head" }, el("div", {}, el("h1", {}, "New swing"),
    el("div", { class: "subtle" }, "Use the original file from your phone so slo-mo keeps its frame rate.")));
  // Hosted: at the swing limit, say so instead of offering an upload that would be refused.
  if (hosted && used >= hosted.max_swings) {
    view.replaceChildren(title,
      el("div", { class: "notice warn" },
        `You already have ${plural(used, "swing")}, the most you can keep. Delete one to add a new swing.`),
      el("a", { class: "btn primary", href: "/" }, "Go to your swings"));
    return;
  }
  let file = null;
  // With face-on held back, down-the-line is the only choice, so preselect it.
  let viewChoice = faceOn ? null : "dtl";
  let hand = rememberedHand();

  const fileName = el("div", { class: "file-status subtle" }, "No video chosen");
  const dropTitle = el("div", { class: "dropzone-title" }, "Choose a video");
  const input = el("input", {
    type: "file", accept: "video/*,.mov,.mp4", id: "file-input", class: "visually-hidden",
    onchange: () => setFile(input.files[0]),
    // A phone can take a while to hand over a video (slo-mo is prepared first): say so.
    onclick: () => {
      fileName.className = "file-status subtle";
      fileName.textContent = "Opening your video… On a phone, a slo-mo clip can take a moment to prepare.";
    },
  });
  input.addEventListener("cancel", () => setFile(file)); // closed the picker: back to what was chosen
  const drop = el("label", { class: "dropzone", for: "file-input" },
    dropTitle,
    el("div", { class: "subtle" }, "or drop it here · .mov or .mp4 · one swing per clip"),
    hosted ? el("div", { class: "subtle small" },
      `Up to ${hosted.max_clip_seconds} seconds and ${hosted.max_upload_mb} MB · `
      + `deleted ${plural(hosted.keep_days, "day")} after upload`) : null,
    fileName);
  drop.addEventListener("dragover", e => { e.preventDefault(); drop.classList.add("over"); });
  drop.addEventListener("dragleave", () => drop.classList.remove("over"));
  drop.addEventListener("drop", e => {
    e.preventDefault();
    drop.classList.remove("over");
    if (e.dataTransfer.files[0]) setFile(e.dataTransfer.files[0]);
  });

  const viewButtons = ["dtl", "fo"].map(v => {
    const unavailable = v === "fo" && !faceOn;
    return el("button", {
      type: "button", class: "choice", "data-view": v, disabled: unavailable,
      onclick: () => { viewChoice = v; refresh(); },
    },
    el("strong", {}, v === "dtl" ? "Down-the-line" : "Face-on"),
    el("span", { class: "subtle" }, v === "dtl" ? "Camera behind you, looking at the target" : "Camera facing you, square to the target line"),
    unavailable ? el("span", { class: "badge soon" }, "Coming in a future release") : null);
  });

  const handButtons = ["right", "left"].map(h => el("button", {
    type: "button", class: "choice", "data-hand": h, onclick: () => { hand = h; refresh(); },
  }, el("strong", {}, HAND_NAMES[h]),
  el("span", { class: "subtle" }, h === "right" ? "Lead with your left side (most golfers)" : "Lead with your right side")));

  const error = el("div", { class: "notice error", hidden: true });
  const agreeBox = hosted ? el("input", { type: "checkbox", id: "agree", onchange: () => refresh() }) : null;
  const submit = el("button", { class: "btn primary", type: "submit", disabled: true }, "Upload and convert");

  function setFile(f) {
    file = f || null;
    error.hidden = true;
    if (file && hosted && file.size > hosted.max_upload_mb * 1024 * 1024) {
      error.textContent = `That video is over ${hosted.max_upload_mb} MB. Trim it to just the swing on your phone, then upload it again.`;
      error.hidden = false;
      file = null;
    }
    fileName.className = file ? "file-status file-ok" : "file-status subtle";
    fileName.textContent = file ? `✓ ${file.name} · ${(file.size / 1e6).toFixed(1)} MB` : "No video chosen";
    dropTitle.textContent = file ? "Video ready · choose a different one" : "Choose a video";
    drop.classList.toggle("chosen", Boolean(file));
    refresh();
  }

  // Says what's still missing, so a grey Upload button isn't a mystery.
  const submitHint = el("span", { class: "subtle small" });

  function refresh() {
    for (const b of viewButtons) b.classList.toggle("selected", b.dataset.view === viewChoice);
    for (const b of handButtons) b.classList.toggle("selected", b.dataset.hand === hand);
    const missing = [!file && "choose a video", !viewChoice && "pick the camera view",
      agreeBox && !agreeBox.checked && "tick the agreement"].filter(Boolean);
    submit.disabled = missing.length > 0;
    submitHint.textContent = missing.length ? `To upload, ${listText(missing)}.` : "";
  }

  const form = el("form", {
    class: "stack",
    onsubmit: async e => {
      e.preventDefault();
      error.hidden = true;
      const progress = progressBlock("Uploading");
      form.replaceWith(progress.node);
      try {
        rememberHand(hand);
        const res = await uploadWithProgress(file, viewChoice, hand, agreeBox ? agreeBox.checked : false,
          // At 100% the server still saves and checks the file: don't leave the bar looking stuck.
          f => (f < 1 ? progress.update(f, `${Math.round(f * 100)}% uploaded`)
            : progress.update(null, "Uploaded. Saving and checking your video…")));
        navigate(swingUrl(res.id));
      } catch (err) {
        progress.node.replaceWith(form);
        error.textContent = err.message;
        error.hidden = false;
      }
    },
  },
  error,
  el("section", { class: "panel" }, el("h2", {}, "1. Video"), input, drop),
  el("section", { class: "panel" }, el("h2", {}, "2. Camera view"), el("div", { class: "choices" }, viewButtons)),
  el("section", { class: "panel" }, el("h2", {}, "3. Golfer"), el("div", { class: "choices" }, handButtons)),
  agreeBox ? el("label", { class: "agree", for: "agree" }, agreeBox,
    el("span", {}, "I agree to the ", el("a", { href: "/terms", target: "_blank" }, "Terms of use"), " and ",
      el("a", { href: "/privacy", target: "_blank" }, "Privacy notice"),
      ", and I have the right to upload this video (it's of me, or of someone who agreed).")) : null,
  el("div", { class: "actions" }, el("a", { class: "btn", href: "/" }, "Cancel"), submit, submitHint));

  view.replaceChildren(title, form);
  refresh();
}
