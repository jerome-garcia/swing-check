// The feedback page (/feedback, linked from the support card, the Terms, and the Privacy notice): a rating from 1 to 5 and an
// optional message. Saved on the server for the maker to read on the admin page; no name,
// email, IP address, or key goes with it.

import { backLink, el, postJSON } from "./util.js";

const MESSAGE_MAX = 1000;
const RATING_WORDS = { 1: "Not useful", 2: "Needs work", 3: "Okay", 4: "Good", 5: "Love it" };

export function renderFeedback(view) {
  let rating = 0;
  const error = el("div", { class: "notice error", hidden: true });
  const message = el("textarea", { class: "feedback-message", rows: 5, maxlength: MESSAGE_MAX,
    placeholder: "What worked, what was confusing, or what you'd like to see (optional)" });
  const count = el("span", { class: "subtle small" });
  const showCount = () => { count.textContent = `${message.value.length} / ${MESSAGE_MAX}`; };
  message.addEventListener("input", showCount);
  showCount();

  const ratingWord = el("span", { class: "subtle small rating-word" }, "Tap a number");
  const buttons = [1, 2, 3, 4, 5].map(n => el("button", {
    type: "button", class: "btn rating-btn", "aria-pressed": "false", "aria-label": `${n}: ${RATING_WORDS[n]}`,
    onclick: () => {
      rating = n;
      for (const [i, b] of buttons.entries()) {
        b.classList.toggle("selected", i + 1 === n);
        b.setAttribute("aria-pressed", String(i + 1 === n));
      }
      ratingWord.textContent = RATING_WORDS[n];
      send.disabled = false;
      error.hidden = true;
    },
  }, String(n)));

  const send = el("button", { class: "btn primary", type: "button", disabled: true, onclick: submit }, "Send feedback");
  const form = el("div", { class: "stack" },
    el("div", { class: "stack-sm" },
      el("strong", {}, "How useful is SwingCheck for you?"),
      el("div", { class: "rating-row" }, buttons),
      el("div", { class: "rating-scale subtle small" }, el("span", {}, "1 = not useful"), ratingWord, el("span", {}, "5 = love it"))),
    el("label", { class: "stack-sm" },
      el("strong", {}, "Anything to tell us?"),
      message,
      count),
    el("p", { class: "subtle small" }, "Please don't include your name, email, or other personal details."),
    error,
    el("div", { class: "actions" }, send));

  async function submit() {
    if (!rating) return;
    send.disabled = true;
    error.hidden = true;
    try {
      await postJSON("/api/feedback", { rating, message: message.value });
      form.replaceChildren(
        el("div", { class: "notice ok" }, "Thanks! Your feedback was sent."),
        el("div", { class: "actions" }, el("a", { class: "btn", href: "/" }, "Back to your swings")));
    } catch (err) {
      error.textContent = err.message;
      error.hidden = false;
      send.disabled = false;
    }
  }

  view.replaceChildren(el("article", { class: "legal feedback" },
    backLink(),
    el("h1", {}, "Send feedback"),
    el("p", { class: "subtle" }, "SwingCheck is new, and your feedback decides what gets better next."),
    form));
}
