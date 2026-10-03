# swing-check

A golf swing analyzer that runs on your own computer. Upload a video of one
swing, say whether it was filmed **down-the-line** or **face-on**, click the
ball (and club), and it gives you an annotated video, key frames and a verdict
for each check. Open it in your browser on the PC, or on your phone over Wi-Fi.

v1 focuses on fat shots, scooping, and wedges/hybrids flying high instead of far.
The down-the-line checks are being rebuilt as a series of checkpoints (address,
swing plane, takeaway, halfway back, top, downswing, impact, follow-through);
address is done so far.

| View | Check | What it tells you |
|---|---|---|
| Down-the-line | **Address posture** | Arms hanging straight down, spine forward bend, knee flex, and whether the back is rounded |
| Face-on | **Hands at impact** | Hands ahead of, level with, or behind the ball (scoop / shaft lean) |
| Face-on | **Weight shift** | How far the hips moved toward the target by impact (low point / fat shots) |
| Face-on | **Head drift** | Whether the head moved away from the target by impact |

Everything runs locally with Python, OpenCV, MediaPipe Pose and ffmpeg. Nothing
is uploaded anywhere.

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

## Starting the app

From the project folder, with the virtual environment active:

```bash
swingcheck
```

Your browser opens at `http://localhost:8765`. Leave the terminal open while you
use the app; press **Ctrl+C** there to stop it.

### Using it from your phone

```bash
swingcheck --phone
```

The terminal prints an address like `http://192.168.1.20:8765`. Open it in your
phone's browser while it's on the **same Wi-Fi** as the PC. Then you can upload a
clip straight from the simulator bay.

- The first time, Windows asks whether to allow Python through the firewall.
  Allow it on **private** networks.
- There is no login: anyone on the same Wi-Fi can open the app while it's
  running with `--phone`. Use it on your home network, and stop it when you're
  done.
- If the app warns that a slo-mo clip came through at 30 fps, your phone
  converted it on upload. Save the video to Files first (Share → Save to Files),
  then pick it from Files in the upload screen.

Other options: `--port 9000` to use a different port, `--no-browser` to not open
a tab, `--runs-dir D:\golf` to store swings elsewhere.

---

## Filming your swing

The app measures positions in the image, so **the camera must not move**
during the clip. A tripod is the single most important thing.

### For every clip

- **Tripod, fixed position.** No zooming, panning or hand-holding. The ball and
  club points you click once are assumed to stay put.
- **One swing per clip.** Extra footage before and after is fine; practice
  swings in the same clip can confuse phase detection. Cut them out with
  **Trim the clip** on the marking screen.
- **Whole body in frame**, including feet, the ball, and room above the head
  for the club at the top. Portrait or landscape both work.
- **Slo-mo (120 or 240 fps) if your phone has it.** 30 fps works, but the hands
  move so fast near impact that the impact frame can be off by a frame or two.
- **Steady, even light.** Avoid strong backlight (a bright window or screen
  behind you).
- **Use the original file.** Sharing or messaging an iPhone slo-mo clip often
  re-exports it at 30 fps. On the PC, use iCloud.com "download original", the
  Windows Photos app import, or a USB copy from the iPhone's DCIM folder. The app
  warns if a clip is 60 fps or slower.
- **Same camera spot every session** (mark the tripod feet with tape). Angles
  and distances are measured in 2D, so moving the camera changes the numbers even
  when your swing doesn't.
- **Reasonably fitted clothing.** A loose shirt changes your outline, which the
  back-rounding check reads.

### Down-the-line

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
  measured angles.
- Distance: far enough that your full swing, including the club at the top, stays
  in frame (often 3 to 4 m).
- Aim the camera straight down the target line, not angled toward you.

### Face-on

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

## Using the app

1. **New swing.** Choose a video (or drop it on the page) and pick
   down-the-line or face-on. It uploads and converts with a progress bar; the
   conversion straightens rotated phone video and keeps the slo-mo frame rate.
2. **Mark your address.** Scrub to your address position with the slider, the
   ‹ › buttons or the arrow keys (Shift = 10 frames). Then click:
   - the **ball** (both views)
   - the **clubhead at the hosel**, where the shaft meets the head (down-the-line)
   - the **grip**, the center of your hands (down-the-line)

   A magnifier follows the cursor; on a phone, touch and hold, slide to aim with
   the magnifier above your finger, and let go to place the point. **Undo**
   removes the last point. In down-the-line, **the frame you mark on is your
   address frame**: the address checks are measured on it, so pick a frame where
   you're fully set up and still.

   **Trim the clip** (below the points) cuts out practice swings or idle time:
   scrub to a frame, press **Start here** or **End here**, then **Apply trim**.
   Your points are kept.
3. **Analyze.** Tracking your body takes about a minute for a few seconds of
   240 fps slo-mo on a laptop, with live progress. You can leave the page and
   come back.
4. **Results.** The annotated video (with 0.25× and 0.5× speeds), a card per
   check with its verdict and numbers, the key frames, and the phases.
   **Report** opens a plain-text summary.

Your swings are listed on the home page, newest first, with their verdicts. Open
one to see it again, **Edit marks** to re-mark, **Re-analyze** after changing
settings, or **Delete** to remove it and its files.

### When a phase is wrong

In **Phases** on the results page, press **Adjust** next to top or impact (and
address, for face-on), scrub to the right frame, and press **Set as …**. The
swing is re-analyzed with your frame, which is remembered. **Reset to
automatic** goes back to detection. In down-the-line, address is the frame you
marked on; change it with **Edit marks**.

### Where your swings are stored

Each swing is a folder in `runs/` in the project. It holds the original upload,
the converted video, your marks, the analysis, `annotated.mp4`, the key frame
images and `report.txt`. Back up or delete that folder like any other files.

---

## Reading the results

Each check reports **OK**, **Watch** (worth a look) or **Flag**, plus the
numbers behind it. Distances are in **body lengths**: your torso length
(shoulders to hips) measured at address. So `0.10` means a tenth of your torso,
roughly 5 cm for most adults, regardless of how far away the camera was.

**Address posture (down-the-line).** Measured on the frame you marked, using
the body points on the camera side (your trail side):

- **Arms:** the shoulder-to-wrist line should hang straight down. Reported in
  degrees from vertical; + means the hands reach out toward the ball, - means
  they're tucked in toward the body.
- **Spine:** forward bend of the hip-to-shoulder line from vertical.
- **Knees:** knee flex, 0 = straight leg.
- **Back:** how far the outline of your back bulges beyond a straight line
  between hip and shoulder level (in body lengths), measured from the body
  silhouette. A rounded upper back (hump) reads higher.

The address key frame draws each line with its value, green when in range and
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
knee_flex_max = 38

[analyzers]
disabled = ["head_drift"]     # skip a check entirely
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

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `ffmpeg not found on PATH` (conversion fails) | Install it (Setup step 2), open a new terminal, and start the app again. |
| Warning that the clip is 30 or 60 fps when you filmed slo-mo | The file was re-exported on the way off the phone. Use the original (see Filming). |
| Phone can't open the app | Start with `swingcheck --phone`, check the phone is on the same Wi-Fi, and allow Python through the Windows firewall on private networks. |
| Address checks measured on the wrong frame | **Edit marks**, scrub to your set-up position, and save again. |
| Back reads rounded but isn't | Loose clothing changes the outline; check the line drawn on the address key frame. |
| Wrong top/impact | **Adjust** it under Phases on the results page. |
| A check says "No data" | A body point wasn't tracked at that moment: usually lighting, part of the body out of frame, or baggy clothing. |
| Practice swing detected instead of the real one | **Edit marks** → **Trim the clip**. |
| Page looks broken after updating the code | Reload the page (Ctrl+R). |

---

## Adding a check

Checks are plug-ins. Create a new file in `swingcheck/analyzers/`; it's picked
up automatically and appears in the app, and nothing else needs to change:

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
(`ctx.side("shoulder", "trail")`), the target direction (`ctx.target_sign`), the
video frame (`ctx.image(frame)`), and body-unit conversion (`ctx.units(px)`).
Overlay kinds are documented in `swingcheck/analyzers/__init__.py`.

---

## Development

Run the tests with `pytest`. Some tests need `ffmpeg` on the PATH and are
skipped without it.

```
swingcheck/
  app/                web app: server, background jobs, swing storage, frontend (static/)
  pipeline.py         convert -> mark -> pose -> phases -> checks -> outputs
  config.py           loads config/default.toml + config/local.toml
  ingest.py           ffmpeg conversion
  pose.py             MediaPipe pose tracking + cache, body silhouette
  body.py             hand path, body scale, cleaned keypoint tracks
  phases.py           address / takeaway / top / early downswing / impact
  geometry.py         line, angle and outline math
  analyzers/          one file per check (auto-discovered)
  output/             annotated video, key frames, report
config/default.toml   every threshold, commented
tests/                unit tests (pytest)
```

## Not in v1

Backswing sway, vertical head movement, early extension, automatic club
detection, and session trends. Each of these can be added as a new check
(see above).
