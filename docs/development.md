# Developer guide

How SwingCheck is put together, and how to change, test, and release it. For
what each checkpoint measures, see [checkpoints.md](checkpoints.md); for the
server, see [hosting.md](hosting.md).

## Getting started

On Windows, install Python 3.11 ([python.org](https://www.python.org/downloads/))
and ffmpeg, then set up the project from its folder:

```bash
winget install Gyan.FFmpeg
```

```bash
py -3.11 -m venv .venv
```

```bash
.venvScriptsctivate
```

```bash
pip install -e ".[dev]"
```

```bash
swingcheck
```

The app opens at `http://localhost:8765`. Open a new terminal after installing
ffmpeg so it's on your PATH. The first analysis downloads the pose model (about
30 MB) into `models/`; after that it works offline. Useful options:

| Option | What it does |
|---|---|
| `--port 8766` | Use another port, so a test copy can run beside your own |
| `--runs-dir <folder>` | Store swings somewhere else, such as a scratch folder for testing |
| `--no-browser` | Don't open a browser tab |
| `--phone` | Listen on your Wi-Fi so your phone can open it (allow Python through the firewall on private networks; anyone on the Wi-Fi can open it) |
| `--hosted` | Run as on swingcheck.org: owner keys, limits, and expiry |

## Project layout

```
swing-check/
  swingcheck/        the app (Python package, plus the web pages in app/static/)
  config/            default.toml: every range and setting, with comments
  tests/             automated tests (pytest)
  docs/              these guides, and release notes in docs/releases/
  branding/          logo, brand guide, link preview, Ko-fi cover
  deploy/            release script, server service file, Caddy config
  samples/           your test videos (not in git)
  runs/              your swings, one folder each (not in git)
  models/            the pose model, downloaded on first use (not in git)
  pyproject.toml     package name, dependencies, and the `swingcheck` command
```

`samples/`, `runs/`, `models/`, and `config/local.toml` stay on your computer;
`.gitignore` keeps them out of git.

## How the code is organized

The easiest way to understand the code is to follow one swing through it:

1. **Upload.** The browser sends the video to the server (`app/server.py`),
   which saves it as a new swing folder (`app/store.py`).
2. **Convert.** ffmpeg turns it into a standard video: upright, slo-mo frame
   rate kept, black bars cropped (`ingest.py`). Long tasks like this run in the
   background, one at a time (`app/jobs.py`).
3. **First look.** A quick pass finds the swing to suggest frames for marking,
   and checks the camera angle (`camera_check.py`).
4. **Marking.** The golfer picks a frame for each step and clicks the ball,
   club, and hands (`app/static/mark.js`). Frames are served by `app/frames.py`.
5. **Analysis.** `pipeline.py` runs the steps in order:
   - track the body on every frame with MediaPipe (`pose.py`), then smooth it
     (`body.py`);
   - find the swing's moments: address, top, impact (`phases.py`);
   - run each check (`analyzers/`), which grades it green, yellow, or red;
   - pick the one fault to work on first (`priority.py`).
6. **Results.** Draw the annotated video and key frames, and write the text
   report and PDF (`output/`). The results page shows them (`app/static/results.js`).

### Python files

| File | What it does |
|---|---|
| `pipeline.py` | Runs the whole analysis, step by step |
| `ingest.py` | Converts uploads with ffmpeg |
| `camera_check.py` | Is this a usable down-the-line view? |
| `pose.py` | Body tracking with MediaPipe, cached per swing |
| `body.py` | Cleans up tracked points; body size, for cm figures |
| `phases.py` | Finds address, top, and impact |
| `checkpoints.py` | The list of 8 checkpoints, in swing order |
| `analyzers/` | One file per check (`dtl_` down the line, `fo_` face-on), found automatically |
| `priority.py` | Picks "Work on first" |
| `geometry.py` | Line, angle, and distance math |
| `config.py` | Reads `config/default.toml`, then your `config/local.toml` |
| `models.py` | Shared data types |
| `output/` | Annotated video, key frames, text report, summary PDF |

### The web app (`swingcheck/app/`)

| File | What it does |
|---|---|
| `server.py` | All the web addresses (`/api/...`) and page routes |
| `store.py` | Swing folders: create, list, read, delete |
| `jobs.py` | Background queue for conversions and analyses |
| `frames.py` | Serves single video frames to the marking screen |
| `hosted.py` | Hosted mode: owner keys, limits, expiry |
| `share.py` | Share PDF links |
| `admin.py` | The `/admin` page: counts and timings only |
| `make_reference.py` | Builds the marking examples (Rory McIlroy, Tiger Woods) |

The pages are plain JavaScript modules in `app/static/`, with no build step:

| File | Page |
|---|---|
| `index.html`, `app.js` | The page shell and routing between pages |
| `history.js` | Your swings (home page) |
| `upload.js`, `setup.js` | New swing, and the camera setup guide |
| `mark.js` | Marking |
| `swing.js`, `results.js` | A swing and its results |
| `legal.js` | Terms of use and Privacy notice |
| `util.js` | Shared helpers, like `listText()` for Oxford-comma lists |
| `style.css` | All styles |

## Tuning

Every range is in [`config/default.toml`](../config/default.toml), each with a
comment. **Don't edit that file** to experiment. Create `config/local.toml` (not
in git) with only what you want to change, restart the app, and **Re-analyze** a
swing to see the new results. A misspelled key stops the app with an error
naming it, so typos aren't silently ignored.

How to tune a range:

1. Film several swings: some good strikes and some of the misses you're working on.
2. Compare their numbers on the results pages.
3. Set the range between the good and bad numbers.
4. Check that the reference swings (McIlroy and Tiger) still read green.

When a change is meant for everyone, move it into `default.toml` and update
[checkpoints.md](checkpoints.md) to match.

Other useful settings:

- `[golfer] torso_cm`: your torso length, for more accurate cm figures.
- `[phases] impact_offset_ms`: shifts the detected impact frame (try `4` to `8`
  at 240 fps if impact is a frame or two early).
- `[output] freeze_frames`: add `"takeaway"` or `"early_downswing"` key frames.
- `[analyzers] disabled`: names of checks to skip, such as `["address"]`.

## Examples

### Change a range

Make the address knee bend stricter, for yourself only, in `config/local.toml`:

```toml
[analyzers.address]
knee_flex_max = 32
```

Restart, re-analyze, and compare. To make it the default, change the same key
in `default.toml`, update [checkpoints.md](checkpoints.md), and run the tests.

### Add a check

Checks are plug-ins. Create a file in `swingcheck/analyzers/` that registers an
analyzer under the **name and phase listed for its checkpoint in
`swingcheck/checkpoints.py`**. It's picked up automatically and appears in the
app. An illustration (not the real top check):

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

Then:

1. Add its settings under `[analyzers.top]` in `config/default.toml`.
2. Describe it in [checkpoints.md](checkpoints.md).
3. Add a test file (`tests/test_top.py`), and update the expected list in
   `tests/test_app.py::test_checkpoint_list_marks_built_ones`.

What the context gives you: body points (`ctx.track(name)` for any MediaPipe
landmark, `ctx.hands()`, `ctx.midpoint(a, b)`), the golfer's marks
(`ctx.marks.points`), frames (`ctx.frame("top")`, `ctx.at(track, "impact")`,
`ctx.value(track, frame, what)`), lead and trail sides
(`ctx.side("shoulder", "trail")`), the picture (`ctx.image(frame)`), and body
units (`ctx.units(px)`). Overlay kinds are documented in
`swingcheck/analyzers/__init__.py`.

### Rebuild a marking example

The examples on the marking screen come from a fully marked swing:

```bash
python -m swingcheck.app.make_reference runs/<swing-folder> "Rory McIlroy"
```

Add `driver` at the end for the driver example. They're saved in
`swingcheck/app/static/reference/` and `reference/driver/`. A few points were
adjusted by hand after building; the docstring in `make_reference.py` lists
them, so put them back after a rebuild.

## Writing style

All text the golfer sees follows the same rules:

- **Plain words first:** *front* and *back* rather than lead and trail;
  *toward you* and *toward the ball* rather than inside and outside.
- **Sentence case** for labels, and full sentences for summaries and tips.
- **Oxford comma** in lists. Build lists in code with `listText()` (JavaScript)
  or `list_text()` (Python).
- **Green, yellow, red** are Good, Watch, and Fix. Distances in whole cm
  (`ctx.distance_text()`), angles in whole degrees (`deg_text()`).
- **Never point golfers to GitHub or these docs:** the app has to explain itself.

## Brand

The one-page brand guide (logo, clear space, colors, type, voice) is
[branding/swingcheck-brand-guide.pdf](../branding/swingcheck-brand-guide.pdf).
The `branding/` folder also holds the logo SVGs, the Ko-fi cover, and the link
preview. Each is built from an HTML file there; edit it and re-render with:

```bash
sh branding/render.sh
```

The link preview (`link-preview.html` → `swingcheck/app/static/og-image.jpg`) is
the picture chat apps show for a swingcheck.org link. Keep it 1200×630 and under
300 KB, or some phones skip it. After changing it, refresh Messenger's copy with
Facebook's Sharing Debugger (developers.facebook.com/tools/debug).

The app is dark by default; the footer's **Light mode** switch changes it. The
footer's Ko-fi link comes from `KOFI_URL` at the top of `app/static/app.js`.

## Branching and merging

`main` is always ready to release. Every change gets its own short branch, is
tested, then merged into `main` and pushed.

1. Start from an up-to-date `main`:

   ```bash
   git switch main
   ```

   ```bash
   git pull --ff-only
   ```

2. Make a branch named after the change:

   ```bash
   git switch -c takeaway-range
   ```

3. Make the change, run the tests (see [Testing](#testing)), and commit:

   ```bash
   git commit -am "Takeaway: green up to 20 cm toward the ball"
   ```

4. Merge into `main` and push:

   ```bash
   git switch main
   ```

   ```bash
   git merge --ff-only takeaway-range
   ```

   ```bash
   git push
   ```

5. Delete the branch:

   ```bash
   git branch -d takeaway-range
   ```

`--ff-only` keeps history in a straight line. If it refuses, `main` moved on
while you worked: switch to your branch, run `git rebase main`, and merge again.

Merging doesn't change the live site. Several merged changes can go out
together in one release.

## Testing

### Automated tests

```bash
pytest -q
```

```bash
ruff check swingcheck tests
```

Both must pass before you commit. Tests that need ffmpeg are skipped without it.
GitHub runs both on every push (`.github/workflows/tests.yml`).

To run one file or one test while working:

```bash
pytest tests/test_takeaway.py -q
```

```bash
pytest -q -k follow_through
```

When you change a check, add or update a test in its `tests/test_<check>.py`.

### Trying it in the browser

Don't test on your own swings: use a scratch copy, so nothing you care about
gets changed.

1. Copy a swing folder from `runs/` into a scratch folder. If you copy a folder
   within the same scratch folder, change the `"id"` in the copy's `swing.json`
   to the new folder name.
2. Start a test copy of the app on another port:

   ```bash
   swingcheck --port 8766 --no-browser --runs-dir <scratch-folder>
   ```

3. Open `http://localhost:8766` and try the change. Check a wide screen and a
   phone-size window, and both dark and light mode if styles changed.
4. Add `--hosted` to test hosted-only behavior (limits, expiry, sharing).

After changing ranges, re-analyze the McIlroy and Tiger swings and check they
still read green.

## Releasing

A release is a git tag on `main`; only releases reach swingcheck.org.

### Versions

Versions look like `v0.6.14-alpha`:

- **Patch** (`0.6.13` → `0.6.14`) for fixes and small tweaks.
- **Minor** (`0.6.14` → `0.7.0`) for new features.

Never move or reuse a tag that has been released.

### Step by step

1. Update the release notes (see [Release notes](#release-notes)) on a branch,
   and merge them into `main`.
2. Make sure `main` is clean and pushed:

   ```bash
   git status
   ```

3. See what's live:

   ```bash
   deploy/deploy.sh
   ```

4. Release (in Git Bash):

   ```bash
   bash deploy/deploy.sh v0.6.15-alpha
   ```

5. Check the site reports the new version:

   ```bash
   curl -s https://swingcheck.org/api/health
   ```

The script tags `main`, waits until no analysis or upload is running (a restart
would lose them), checks the tag out on the server, reinstalls if
`pyproject.toml` changed, restarts the app, and checks the site reports the new
version. Browsers load the new CSS and JS straight away; no hard refresh is
needed.

**Rolling back** is releasing the previous tag again:

```bash
bash deploy/deploy.sh v0.6.14-alpha
```

Never edit code on the server: it only runs tags from GitHub. The one thing done
by hand is installing new system packages (`apt install …`); note them in
[hosting.md](hosting.md).

## Release notes

Each minor version has one page in [docs/releases/](releases/), such as
`v0.6.md`, rendered to a PDF. A new minor version gets a new file; a patch adds
to the current one.

1. Edit `docs/releases/v0.6.md`:
   - update the "Released … · v0.6.0 to v0.6.N" line;
   - add the patch under **Fixes and tweaks**, in plain words. Small patches
     can share one bullet (for example "v0.6.12 to v0.6.14").
2. Render the PDF (Windows, uses Edge):

   ```bash
   python docs/releases/render.py v0.6.md
   ```

3. Commit both files, merge, and push before releasing.

Each page has a title, the "Released" line, a one-line intro, then **What's
new** and **Fixes and tweaks** as bullets. Keep it to one A4 page.
