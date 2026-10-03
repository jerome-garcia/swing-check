import { el, progressBlock, swingUrl } from "./util.js";

// Upload with XMLHttpRequest: fetch() can't report upload progress.
function uploadWithProgress(file, viewChoice, onProgress) {
  return new Promise((resolve, reject) => {
    const form = new FormData();
    form.append("file", file);
    form.append("view", viewChoice);
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

export function renderUpload(view) {
  let file = null;
  let viewChoice = null;

  const fileName = el("div", { class: "subtle" }, "No video chosen");
  const input = el("input", {
    type: "file", accept: "video/*,.mov,.mp4", id: "file-input", class: "visually-hidden",
    onchange: () => setFile(input.files[0]),
  });
  const drop = el("label", { class: "dropzone", for: "file-input" },
    el("div", { class: "dropzone-title" }, "Choose a video"),
    el("div", { class: "subtle" }, "or drop it here · .mov or .mp4 · one swing per clip"),
    fileName);
  drop.addEventListener("dragover", e => { e.preventDefault(); drop.classList.add("over"); });
  drop.addEventListener("dragleave", () => drop.classList.remove("over"));
  drop.addEventListener("drop", e => {
    e.preventDefault();
    drop.classList.remove("over");
    if (e.dataTransfer.files[0]) setFile(e.dataTransfer.files[0]);
  });

  const viewButtons = ["dtl", "fo"].map(v => el("button", {
    type: "button", class: "choice", "data-view": v,
    onclick: () => { viewChoice = v; refresh(); },
  },
  el("strong", {}, v === "dtl" ? "Down-the-line" : "Face-on"),
  el("span", { class: "subtle" }, v === "dtl" ? "Camera behind you, looking at the target" : "Camera facing you, square to the target line")));

  const error = el("div", { class: "notice error", hidden: true });
  const submit = el("button", { class: "btn primary", type: "submit", disabled: true }, "Upload and convert");

  function setFile(f) {
    file = f || null;
    fileName.textContent = file ? `${file.name} · ${(file.size / 1e6).toFixed(1)} MB` : "No video chosen";
    drop.classList.toggle("chosen", Boolean(file));
    refresh();
  }

  function refresh() {
    for (const b of viewButtons) b.classList.toggle("selected", b.dataset.view === viewChoice);
    submit.disabled = !(file && viewChoice);
  }

  const form = el("form", {
    class: "stack",
    onsubmit: async e => {
      e.preventDefault();
      error.hidden = true;
      const progress = progressBlock("Uploading");
      form.replaceWith(progress.node);
      try {
        const res = await uploadWithProgress(file, viewChoice,
          f => progress.update(f, `${Math.round(f * 100)}% uploaded`));
        location.hash = swingUrl(res.id);
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
  el("div", { class: "actions" }, el("a", { class: "btn", href: "#/" }, "Cancel"), submit));

  view.replaceChildren(
    el("div", { class: "page-head" }, el("div", {}, el("h1", {}, "New swing"),
      el("div", { class: "subtle" }, "Use the original file from your phone so slo-mo keeps its frame rate."))),
    form);
}
