# swing-check

A local command-line golf swing analyzer. Give it one video of one swing, say
whether it was filmed **down-the-line** (`dtl`) or **face-on** (`fo`), and it
produces an annotated video, freeze frames and a short text report.

v1 focuses on fat shots, scooping, and wedges/hybrids flying high instead of far.
The down-the-line checks are being rebuilt as a series of checkpoints (address,
swing plane, takeaway, halfway back, top, downswing, impact, follow-through);
address is done so far.

| View | Check | What it tells you |
|---|---|---|
| DTL | **Address posture** | Arms hanging straight down, spine forward bend, knee flex, and whether the back is rounded |
| Face-on | **Hands at impact** | Hands ahead of, level with, or behind the ball (scoop / shaft lean) |
| Face-on | **Weight shift** | How far the hips moved toward the target by impact (low point / fat shots) |
| Face-on | **Head drift** | Whether the head moved away from the target by impact |

Everything runs on your machine with Python, OpenCV, MediaPipe Pose and ffmpeg.

---

## Setup (Windows)

1. **Python 3.10+** ([python.org](https://www.python.org/downloads/)). Check with `py --version`.
2. **ffmpeg**:

   ```bash
   winget install Gyan.FFmpeg
   ```

   Open a **new** terminal afterwards so `ffmpeg` is on your PATH.
3. **Install swing-check** from the project folder:

   ```bash
   py -3 -m venv .venv
   ```

   ```bash
   .venv\Scripts\activate
   ```

   ```bash
   pip install -e ".[dev]"
   ```

The first analysis downloads the MediaPipe pose model (about 30 MB) into
`models/`. After that, everything works offline.

Run the tests with `pytest`.

---

## Filming your swing

The tool measures positions in the image, so **the camera must not move**
during the clip. A tripod is the single most important thing.

### For every clip

- **Tripod, fixed position.** No zooming, panning or hand-holding. The ball and
  club points you click once are assumed to stay put.
- **One swing per clip.** Extra footage before and after the swing is fine;
  practice swings in the same clip can confuse phase detection. Trim them with
  `--start` / `--end`.
- **Whole body in frame**, including feet, the ball, and room above the head
  for the club at the top. Portrait or landscape both work.
- **Slo-mo (120 or 240 fps) if your phone has it.** 30 fps works, but the hands
  move so fast near impact that the impact frame can be off by a frame or two.
- **Steady, even light.** Avoid strong backlight (a bright window or screen
  behind you).
- **Copy the original file.** Sharing or messaging an iPhone slo-mo clip often
  re-exports it at 30 fps. Use iCloud.com "download original", the Windows
  Photos app import, or a USB copy from the iPhone's DCIM folder. The tool warns
  if a clip is 60 fps or slower.
- **Use the same camera spot every session** (mark the tripod feet with tape).
  Angles and distances are measured in 2D, so moving the camera changes the
  numbers even when your swing doesn't.

### Down-the-line (`--view dtl`)

```
            target
              ^
              |
     ball o   |   target line
              |
    golfer    |
              |
              |
           [camera]   on the line through your hands, parallel to the target line
```

- Stand behind yourself, looking **toward the target**.
- Put the camera **on the line through your hands at address**, parallel to the
  target line (not on the ball-to-target line, which hides the hands behind the
  body).
- Height: about **hand/hip height** (roughly 1 m). Higher or lower changes the
  measured angles (spine bend, plane lines).
- Distance: far enough that your full swing, including the club at the top, stays
  in frame (often 3 to 4 m).
- Aim the camera straight down the target line, not angled toward you.

### Face-on (`--view fo`)

```
       target <-- (for a left-hander)        (for a right-hander) --> target

                    golfer
                      |
                    ball o
                      |
                      |
                   [camera]   square to the target line, facing your chest
```

- The camera faces you, **square to the target line**.
- Center it on the **ball / your sternum**, at about **chest height**.
- For a right-hander the target is on the **right of the screen**; for a
  left-hander, the left. Set your handedness in the config (see Tuning). If
  your setup is unusual, set `target_direction_fo` explicitly.
- Distance: full body plus the club at the top in frame (often 3 to 4 m).

---

## Usage

```bash
swingcheck samples/my_swing.mov --view dtl
```

What happens:

1. **Normalize.** The clip is converted to an upright, constant-frame-rate MP4
   (rotation and variable frame rate handled; slo-mo frame rate kept).
2. **Mark points.** A window opens on the first frame. Scrub to your address
   position and click:
   - **ball** (both views)
   - **clubhead at the hosel**, where the shaft meets the head (DTL)
   - **grip**, the center of your hands (DTL)

   Press **Enter** to save. A magnifier in the corner helps you click
   precisely. In DTL, **the frame you mark on is your address frame**: the
   address posture checks are measured on it, so pick a frame where you're
   fully set up and still.

   | Key | Action |
   |---|---|
   | `a` / `d` or left / right | step 1 frame |
   | `A` / `D` or up / down | step 10 frames |
   | click | place the next point |
   | `u` or Backspace | undo last point |
   | Enter or Space | save (once all points are placed) |
   | Esc or `q` | cancel |

   The window opens sized to your screen; drag its edges to resize it.
3. **Pose.** MediaPipe finds your body in each frame. For high-frame-rate clips,
   a quick pass locates the swing first and only that stretch is processed at full
   frame rate. Expect about a minute for a few seconds of 240 fps on a laptop CPU.
4. **Phases.** Address, takeaway, top, early downswing and impact are found from
   the hand path.
5. **Checks** for the view run, and the outputs are written.

Everything is cached in `runs/<clip name>/`. Rerunning the same clip skips the
slow stages and doesn't ask you to click again.

### Options

| Option | Use |
|---|---|
| `--view dtl` / `--view fo` | Camera view (required) |
| `--start 5 --end 12` | Trim to this time range (seconds) before analysis |
| `--remark` | Open the marking window again even though marks are saved |
| `--address N --top N --impact N` | Override detected phase frames (see below) |
| `--auto-phases` | Forget saved overrides and use automatic detection |
| `--no-video` | Skip the annotated video (faster; images and report only) |
| `--pose-debug` | Also write `pose_debug.mp4` with the detected skeleton drawn |
| `--force` | Redo every stage, ignoring the cache |
| `--config my.toml` | Extra config file for this run |
| `--runs-dir DIR` | Put outputs somewhere other than `runs/` |

### Outputs (`runs/<clip name>/`)

| File | Contents |
|---|---|
| `annotated.mp4` | The swing with plane/reference lines, the hand path (blue backswing, pink downswing, grey follow-through), checkpoint markers, verdicts and phase labels. Slo-mo clips play back slowed (240 fps plays at 60 fps, 4x slow). |
| `address.png`, `top.png`, `impact.png` | Freeze frames with the same annotations |
| `summary.png` | The freeze frames side by side |
| `report.txt` | Phases, every check's verdict and measurements, and a summary of what was flagged |
| `analysis.json` | The same results, machine-readable |
| `marks.json`, `phases.json`, `pose.json`, `video.json`, `normalized.mp4` | Cached intermediate data |

### When a phase is wrong

Find the right frame number: it's in the footer of every frame of
`annotated.mp4`, and in the top-left corner of `pose_debug.mp4` (written with
`--pose-debug`, which covers the whole clip). Then:

```bash
swingcheck samples/my_swing.mov --view fo --impact 412
```

Overrides are saved and reused on later runs; the takeaway and early-downswing
checkpoints are recalculated from them. `--auto-phases` clears them. Frame
numbers refer to the normalized (and trimmed, if you used `--start`) video, the
same numbers the footer shows.

---

## Reading the results

Each check reports **OK**, **WATCH** (worth a look) or **FLAG**, plus the
numbers behind it. Distances are in **body lengths**: your torso length
(shoulders to hips) measured at address. So `0.10` means a tenth of your torso,
roughly 5 cm for most adults, regardless of how far away the camera was.

**Address posture (DTL).** Measured on the frame you marked, using the body
points on the camera side (your trail side):

- **Arms:** the shoulder-to-wrist line should hang straight down. Reported in
  degrees from vertical; + means the hands reach out toward the ball, - means
  they're tucked in toward the body.
- **Spine:** forward bend of the hip-to-shoulder line from vertical.
- **Knees:** knee flex, 0 = straight leg.
- **Back:** how far the outline of your back bulges beyond a straight line
  between hip and shoulder level (in body lengths), measured from the body
  silhouette. A rounded upper back (hump) reads higher. Wear reasonably fitted
  clothing; a loose shirt can add to it.

The address freeze frame draws each line with its value, green when in range and
red when not.

**Hands at impact (face-on).** Hands relative to the ball, toward the target.
Ahead = forward shaft lean (good for irons/wedges). Behind = the shaft is leaning
back (scooping), which adds loft and moves the low point back. Also reports the
same number at address and the change between them.

**Weight shift (face-on).** How far your hip center moved toward the target from
address to impact. Too little means the low point is likely behind the ball (fat
shots). Also reports the movement at the top.

**Head drift (face-on).** How far your head center (nose and ears) moved along
the target line from address to impact. Moving away from the target is flagged.

---

## Tuning

All thresholds are in [`config/default.toml`](config/default.toml), each with a
comment. **Don't edit that file.** Create `config/local.toml` (ignored by git)
with only what you want to change:

```toml
[golfer]
handedness = "right"          # or "left"

[analyzers.hands_at_impact]
ahead_threshold = 0.08
behind_threshold = -0.03

[analyzers.weight_shift]
min_shift = 0.12

[analyzers.address]
knee_flex_max = 35

[analyzers]
disabled = ["head_drift"]     # skip a check entirely
```

A misspelled key is reported as an error rather than silently ignored.

How to tune:

1. Film several swings: some good strikes and some of the misses you're working on.
2. Run them all and compare the numbers in each `report.txt`.
3. Set each threshold between your good and bad numbers.

Starting values are reasonable guesses, not calibrated on your swing.

Other useful settings:

- `[phases] impact_offset_ms`: shifts the detected impact frame. Hands bottom out
  slightly before contact, so if impact is consistently a frame or two early on
  your clips, try `4` to `8` at 240 fps.
- `[marking] screen_fraction`: the marking window's starting size.
- `[output] freeze_frames`: add `"takeaway"` or `"early_downswing"` for DTL.
- `[output] max_playback_fps`: how slowed-down slo-mo videos play.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `ffmpeg not found on PATH` | Install it (Setup step 2) and open a new terminal. |
| Warning that the clip is 30 or 60 fps when you filmed slo-mo | The file was re-exported on the way off the phone. Copy the original (see Filming). |
| Address checks measured on the wrong frame | Re-mark with `--remark` and scrub to your set-up position before clicking. |
| Back reads rounded but isn't | Loose clothing changes the silhouette; check the outline on `address.png`. |
| Wrong address/top/impact | Override with `--address/--top/--impact`. |
| Checks say "no data" | A body point wasn't tracked at that phase. Run `--pose-debug` and check the skeleton; usually lighting, a partly out-of-frame body, or baggy clothing. |
| Marking window too big | Lower `[marking] screen_fraction` in `config/local.toml`, or drag the window edges. |
| Practice swing detected instead of the real one | Trim with `--start` / `--end`. |

---

## Adding a check

Checks are plug-ins. Create a new file in `swingcheck/analyzers/`; it's picked
up automatically, and nothing else needs to change:

```python
# swingcheck/analyzers/fo_sway.py
from swingcheck.analyzers import STATUS_COLORS, Overlay, SwingContext, Verdict, register

@register("sway", view="fo", title="Backswing sway")
def sway(ctx: SwingContext) -> Verdict:
    hips = ctx.midpoint("left_hip", "right_hip")
    moved = ctx.units((ctx.at(hips, "top")[0] - ctx.at(hips, "address")[0]) * -ctx.target_sign)
    flagged = moved > ctx.cfg["max_sway"]          # from [analyzers.sway] in the config
    status = "flag" if flagged else "ok"
    return Verdict(
        status=status,
        label="swayed" if flagged else "stable",
        summary="Hips moved away from the target in the backswing." if flagged else "Hips stayed centered.",
        measurements={"sway": round(moved, 3)},
        overlays=[Overlay("point", [tuple(ctx.at(hips, "top"))], STATUS_COLORS[status], "hips @ top",
                          frames=(ctx.frame("top"), len(hips) - 1))],
    )
```

Then add its thresholds under `[analyzers.sway]` in `config/default.toml`.

The context gives you the pose (`ctx.track(name)` for any MediaPipe landmark,
`ctx.hands()`, `ctx.midpoint(a, b)`), your marks (`ctx.marks.points`), phase
frames (`ctx.frame("top")`, `ctx.at(track, "impact")`), lead/trail sides
(`ctx.side("shoulder", "trail")`), the target direction (`ctx.target_sign`), and
body-unit conversion (`ctx.units(px)`). Overlay kinds are documented in
`swingcheck/analyzers/__init__.py`.

---

## Project layout

```
swingcheck/
  cli.py              command-line entry point, runs the pipeline
  config.py           loads config/default.toml + config/local.toml
  ingest.py           ffmpeg normalization
  marking.py          click-to-mark window
  pose.py             MediaPipe pose extraction + cache
  body.py             hand path, body scale, cleaned keypoint tracks
  phases.py           address / takeaway / top / early downswing / impact
  geometry.py         line and plane math
  analyzers/          one file per check (auto-discovered)
  output/             annotated video, freeze frames, report
config/default.toml   every threshold, commented
tests/                unit tests (pytest)
```

## Not in v1

Backswing sway, vertical head movement, early extension, automatic club
detection, and session trends. Each of these can be added as a new check
(see above).
