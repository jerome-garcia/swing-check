# Development

Run the tests with `pytest` and the linter with `ruff check swingcheck tests`
(both come with `pip install -e ".[dev]"`). Some tests need `ffmpeg` on the PATH
and are skipped without it. GitHub runs both on every push
(`.github/workflows/tests.yml`), with ffmpeg installed.

**Branches and releases.** `main` is always releasable. Each change is made on its
own short branch (`git switch -c upload-feedback`), tested locally, then merged into
`main`. A release is a tag on `main` (`v0.2.0-alpha`), and only releases reach the
server; several merged changes can go out as one release.

**Releasing.** From the repo, in Git Bash:

```bash
deploy/deploy.sh                 # what's live, and the latest releases
deploy/deploy.sh v0.2.0-alpha    # tag main (clean and pushed) and deploy it
deploy/deploy.sh v0.1.0-alpha    # an existing tag deploys as is: this is a rollback
```

It waits until no analysis or upload is in progress (a restart loses them; it asks
`/api/health`), checks the tag out on the server, reinstalls if `pyproject.toml`
changed, restarts the service and checks that the site, through Cloudflare, reports
the new version (shown small under the name in the header, from `git describe`).
The page loads its CSS and JS as `style.css?v=<fingerprint of their contents>` (an
import map covers the modules app.js imports), so after a release browsers fetch the
new files instead of mixing in cached old ones; no Ctrl+F5 needed. Never edit
code on the server: it only ever runs a tag from GitHub. New system packages
(`apt install …`) are the one thing to do by hand, and to note in the README.

The app's footer Ko-fi link comes from `KOFI_URL` at the top of
`swingcheck/app/static/app.js` (empty hides it).

```
swingcheck/
  app/                web app: server, background jobs, swing storage, frontend (static/)
    make_reference.py builds the marking examples: McIlroy (iron) in static/reference/, Tiger (driver) in reference/driver/
    hosted.py         hosted mode (--hosted): owner-key privacy, swing limits, expiry
  pipeline.py         convert -> mark -> pose -> phases -> checks -> outputs
  camera_check.py     after upload: is it a usable down-the-line view?
  config.py           loads config/default.toml + config/local.toml
  ingest.py           ffmpeg conversion
  pose.py             MediaPipe pose tracking + cache, body silhouette
  body.py             hand path, body scale, cleaned keypoint tracks
  phases.py           address / takeaway / top / early downswing / impact
  checkpoints.py      the 8 down-the-line checkpoints, in swing order
  priority.py         picks the one fault to work on first
  geometry.py         line, angle and outline math
  analyzers/          one file per check (auto-discovered)
  output/             annotated video, key frames, report
config/default.toml   every threshold, commented
tests/                unit tests (pytest)
```

## Tuning

All thresholds are in [`config/default.toml`](../config/default.toml), each with a
comment. **Don't edit that file.** Create `config/local.toml` (ignored by git)
with only what you want to change:

```toml
[golfer]
torso_cm = 46                 # your torso, for the cm figures

[analyzers.address]
knee_flex_max = 38
back_bulge_max = 0.08

[analyzers]
disabled = []                 # names of checks to skip, e.g. ["address"]
```

**Restart the app** (Ctrl+C, then `swingcheck`) after changing the config, then
**Re-analyze** a swing to see the new verdicts. A misspelled key stops the app
from starting with an error naming it, rather than being silently ignored.

How to tune:

1. Film several swings: some good strikes and some of the misses you're working on.
2. Compare their numbers on the results pages.
3. Set each threshold between your good and bad numbers.

Starting values are reasonable guesses, not calibrated on your swing.

Other useful settings:

- `[phases] impact_offset_ms`: shifts the detected impact frame. Hands bottom out
  slightly before contact, so if impact is consistently a frame or two early on
  your clips, try `4` to `8` at 240 fps.
- `[output] freeze_frames`: add `"takeaway"` or `"early_downswing"` to the key frames.
- `[output] max_playback_fps`: how slowed-down slo-mo plays in the annotated video.

## Adding a check

Checks are plug-ins. To build one of the down-the-line checkpoints, create a
file in `swingcheck/analyzers/` that registers an analyzer under the **name and
phase listed for that checkpoint in `swingcheck/checkpoints.py`**. It's picked
up automatically and appears in the app's checkpoint stepper; nothing else
needs to change. An illustration (not the real top-of-backswing check):

```python
# swingcheck/analyzers/dtl_top.py
from swingcheck.analyzers import STATUS_COLORS, Overlay, Row, SwingContext, Verdict, deg_text, grade, register
from swingcheck.geometry import angle_between_deg

@register("top", view="dtl", title="Top", phase="top")  # name and phase from checkpoints.py
def top(ctx: SwingContext) -> Verdict:
    cfg = ctx.cfg  # [analyzers.top] in the config
    f = ctx.frame("top")
    shoulder = ctx.value(ctx.track(ctx.side("shoulder", "lead")), f, "front shoulder")
    wrist = ctx.value(ctx.track(ctx.side("wrist", "lead")), f, "front wrist")
    hip = ctx.value(ctx.track(ctx.side("hip", "lead")), f, "front hip")
    angle = angle_between_deg(wrist - shoulder, hip - shoulder)
    status = grade(angle, cfg["min"], cfg["max"], cfg["watch_min"], cfg["watch_max"])  # green / yellow / red
    label = "Front arm square to your body" if status == "ok" else "Front arm off square"
    return Verdict(
        status=status,
        label=label,                                                     # sentence case, no period
        summary=f"At the top, your front arm is {deg_text(angle)} from your body.",  # a full sentence
        tip="" if status == "ok" else "Keep your front arm across your chest as you turn.",
        measurements={"front_arm_to_torso_deg": round(angle, 1)},        # saved with the analysis
        rows=[Row("Front arm vs body", deg_text(angle), label.removeprefix("Front arm ").capitalize(), status,
                  good=f"{cfg['min']:g}–{cfg['max']:g}°",                # the card's Good line
                  fix=f"under {cfg['watch_min']:g}° or over {cfg['watch_max']:g}°")],  # and its Fix line
        overlays=[Overlay("segment", [tuple(shoulder), tuple(wrist)], STATUS_COLORS[status], frames=(f, f))],
    )
```

Then add its settings under `[analyzers.top]` in `config/default.toml`, mark it
✅ in [checkpoints.md](checkpoints.md), and update the expected list in
`tests/test_app.py::test_checkpoint_list_marks_built_ones`.

Keep the app's wording and drawing style: plain words (*front* / *back*,
*toward you* / *toward the ball*, golf terms in brackets in the summary),
distances with `ctx.distance_text()` (whole cm) and angles with `deg_text()`,
each row's ranges in its `good` and `fix`, sentence case for labels and notes,
and full sentences for summaries and tips. Draw marks with `clubhead_mark()`,
`hands_mark()` and `spot_mark()`, in the colors under **Reading the drawings**.

The context gives you the pose (`ctx.track(name)` for any MediaPipe landmark,
`ctx.hands()`, `ctx.midpoint(a, b)`), your marks (`ctx.marks.points`), phase
frames (`ctx.frame("top")`, `ctx.at(track, "impact")`, `ctx.value(track, frame,
what)`), lead/trail sides (`ctx.side("shoulder", "trail")`), the video frame
(`ctx.image(frame)`), and body-unit conversion (`ctx.units(px)`).
Overlay kinds are documented in `swingcheck/analyzers/__init__.py`.

## Release notes

One page per release, as a PDF in [docs/releases/](releases/): what each minor
version added, with its patch releases. The PDFs are made from the Markdown beside
them (`vX.Y.md`); edit one or add the next and run `python docs/releases/render.py`
(Windows, uses Edge like the branding pages).

## Brand

The one-page brand guide (logo, versions, clear space, colors, type, voice) is
[branding/swingcheck-brand-guide.pdf](../branding/swingcheck-brand-guide.pdf).
The `branding/` folder also holds the logo SVGs, the Ko-fi cover, and the link
preview (`link-preview.html` → `swingcheck/app/static/og-image.jpg`, 1200×630, kept
under 300 KB because phones that build previews themselves skip bigger images: the
image Messenger, Facebook, and other apps show for a swingcheck.org link, set by the
Open Graph tags in `index.html`). All are built from HTML files there; edit one and
re-render with `sh branding/render.sh`.

The app is dark by default (on every device, whatever the system setting); the
footer's **Light mode** switch changes it, remembered in that browser. After changing the preview, Facebook's Sharing
Debugger (developers.facebook.com/tools/debug) refreshes the copy Messenger keeps.

## Marking examples

Rebuild the examples from any fully marked swing with `python -m swingcheck.app.make_reference runs/<swing-folder> "Name"` (add `driver` at the end for the driver example). They live in `swingcheck/app/static/reference/` and `reference/driver/`.
