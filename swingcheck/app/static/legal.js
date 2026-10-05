// Terms of use and privacy notice, shown in the app (#/terms, #/privacy).
// TERMS_VERSION is recorded with each hosted upload (the visitor agreed to this version);
// change it whenever the wording of either page changes.

import { el, features, plural } from "./util.js";

export const TERMS_VERSION = "2026-10-05";
const UPDATED = "October 5, 2026";
const contact = () => el("a", { href: "https://ko-fi.com/jeromegarcia", target: "_blank", rel: "noopener" }, "the SwingCheck Ko-fi page");

const section = (title, ...body) => el("section", { class: "legal-section" }, el("h2", {}, title), ...body);
const p = (...text) => el("p", {}, ...text);
const list = (...items) => el("ul", {}, items.map(i => el("li", {}, i)));

function terms(hosted) {
  return [
    p("These terms apply whenever you use SwingCheck, whether on this website or on your own computer. By using it, ",
      "you agree to them. If you don't agree, please don't use SwingCheck."),
    section("What SwingCheck is",
      p("SwingCheck is a free tool that estimates golf swing positions from a video you provide. It's for personal ",
        "practice and general information only. It is not professional golf coaching, and it is not medical, ",
        "physical therapy or fitness advice.")),
    section("Results are estimates",
      p("Every measurement, verdict and tip is an automatic estimate from a phone video. Camera angle, lighting, ",
        "clothing, frame rate and where you click all affect the results, and they can be wrong. Don't rely on ",
        "SwingCheck as your only guide for changing your swing.")),
    section("Practice safely",
      p("Golf can cause injury, especially when changing your swing. Warm up, practice within your ability, and ",
        "ask a qualified coach or medical professional before making changes, particularly if you have pain or an ",
        "injury. You're responsible for how you use the results.")),
    section("No warranty",
      p("SwingCheck is provided \"as is\" and \"as available\", without warranties of any kind, express or implied, ",
        "including accuracy, fitness for a particular purpose, availability and non-infringement.")),
    section("Limitation of liability",
      p("To the fullest extent the law allows, the maker of SwingCheck is not liable for any injury, loss or damage ",
        "of any kind, direct or indirect, that comes from using or not being able to use SwingCheck, from relying ",
        "on its results, or from the loss of any video or result. Where the law doesn't allow this to be excluded ",
        "entirely, liability is limited to the amount you paid to use SwingCheck, which is zero.")),
    section("Your videos",
      list(
        "Only upload videos that you have the right to upload: of yourself, or of people who have agreed to it.",
        "Anyone under 18 needs a parent or guardian's permission to use SwingCheck or to be in an uploaded video.",
        "Don't upload anything unlawful, offensive or unrelated to a golf swing, and don't try to access other people's swings or disrupt the service.",
        "You keep all rights to your videos. You allow SwingCheck to store and process them only to show you your results.")),
    hosted ? section("The online service",
      p(`Swings are deleted automatically ${plural(hosted.keep_days, "day")} after upload, and each visitor can keep up to `,
        `${plural(hosted.max_swings, "swing")}. The service can be slow, pause, lose work in progress, change or stop at any `,
        "time without notice. Keep your own copy of anything you want to keep, such as the PDF summary.")) : null,
    section("Example images",
      p("The marking screen shows frames of a professional golfer only as an illustration of each position, for ",
        "comparison. SwingCheck is not affiliated with, sponsored or endorsed by that golfer or any broadcaster, ",
        "tour or brand. Names and images belong to their owners.")),
    section("Tips",
      p("Tips through Ko-fi or InstaPay are voluntary gifts to help cover running costs. They don't buy a service, ",
        "features or support, and they aren't refundable. The payment providers handle them under their own terms.")),
    section("Changes and contact",
      p("These terms may change; the date below shows the latest version, and using SwingCheck after a change means ",
        "you accept it. These terms are governed by the laws of the Republic of the Philippines. Questions? Message ",
        "the maker through ", contact(), ".")),
  ];
}

function privacy(hosted) {
  if (!hosted) {
    return [
      p("This copy of SwingCheck runs on your own computer. Your videos, marks and results stay in its swings folder ",
        "on this computer and are never uploaded anywhere. SwingCheck has no accounts, analytics or ads."),
      section("Questions", p("Message the maker through ", contact(), ".")),
    ];
  }
  return [
    p("SwingCheck is built to know as little about you as possible: there are no accounts, no names or emails, ",
      "no analytics, no ads and no third-party trackers."),
    section("What's stored",
      list(
        "Your video, and what's made from it: frames, the annotated video, your marks and the results.",
        "The video's file name and the time you uploaded it.",
        "A random key in a cookie, which is how SwingCheck knows which swings are yours. The server keeps only a scrambled fingerprint of it, next to your swings.")),
    section("Why",
      p("Only to analyze your swing and show the results to you. Your videos aren't sold, shared, used for ",
        "advertising or used to train anything.")),
    section("Who can see your swings",
      p("Only browsers with your key: this one, and any device where you open your private link. Anyone you give ",
        "that link to can see and delete your swings, so keep it private.")),
    section("How long it's kept",
      p(`Every swing is deleted automatically ${plural(hosted.keep_days, "day")} after upload, or straight away when you `,
        "delete it. The cookie stays in your browser until you clear it, but by then it points to nothing.")),
    section("Service providers",
      p("SwingCheck runs on a rented server, and a network provider protects and speeds up the site. Like any ",
        "website, they may keep short-lived technical logs, such as IP addresses, for security. Tips are handled ",
        "by Ko-fi, or by your GCash, Maya or bank app for InstaPay, under their own privacy policies.")),
    section("Your choices",
      p("You can delete any swing at any time with Delete swing. Since SwingCheck doesn't know who you are, that's ",
        "also how to remove your data. For anything else, message the maker through ", contact(), ".")),
    section("Changes", p("This notice may change; the date below shows the latest version.")),
  ];
}

export async function renderLegal(view, page, isCurrent) {
  const { hosted } = await features();
  if (!isCurrent()) return;
  const isTerms = page === "terms";
  view.replaceChildren(el("article", { class: "legal" },
    el("a", { class: "back", href: "#/" }, "← Your swings"),
    el("h1", {}, isTerms ? "Terms of use" : "Privacy notice"),
    ...(isTerms ? terms(hosted) : privacy(hosted)).filter(Boolean),
    el("p", { class: "subtle small" }, `Last updated ${UPDATED}.`)));
}
