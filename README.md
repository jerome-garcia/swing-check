# swing-check

A golf swing analyzer that runs on your own computer. Upload a **down-the-line**
video of one swing, click the ball and club, and it gives you an annotated
video, key frames and a verdict for each check. Open it in your browser on the
PC, or on your phone over Wi-Fi.

The goal is to fix fat shots, scooping, and wedges/hybrids flying high instead
of far. The down-the-line analysis is being built as **eight checkpoints**
through the swing; see [Roadmap](#roadmap) for what each one checks and which
are done. **Face-on** analysis is held back for a future release.

Everything runs locally with Python, OpenCV, MediaPipe Pose and ffmpeg. Nothing
is uploaded anywhere.

---

## Roadmap

### Down-the-line checkpoints

Built one at a time, in this order. Each checkpoint is checked on its own frame
of the swing.

| # | Checkpoint | What it checks | Status |
|---|---|---|---|
| 1 | **Address / alignment** | Arms perpendicular to the ground, spine tilt at the right angle, knee bend correct (plus back rounding) | ✅ Implemented |
| 2 | **Swing plane** | At address, a line through the clubhead and shaft points you click is the swing plane; check that its angle is correct and that it points roughly at the belt buckle | ✅ Implemented |
| 3 | **Takeaway** | When the club is parallel to the target line in the takeaway, the club should cover the hands | ⬜ Not yet |
| 4 | **Backswing (halfway back)** | The hands should split the biceps, and the club should point back inside the golf ball | ⬜ Not yet |
| 5 | **Top of backswing** | The lead (left) arm matches the shoulders, 90° to the spine, and the club is on plane | ⬜ Not yet |
| 6 | **Downswing** | The club comes back down the plane; check shallowing | ⬜ Not yet |
| 7 | **Impact** | (details to be defined) | ⬜ Not yet |
| 8 | **Follow-through** | The club exits on the same line the golfer had in the backswing | ⬜ Not yet |

**1. Address / alignment (implemented).** Measured on the frame you mark on,
which is the address frame for down-the-line, using the body points on the
camera side (your trail side). Settings live in `[analyzers.address]` in
`config/default.toml`.

| Measurement | How | Good range (default) |
|---|---|---|
| Arms hang straight down | shoulder → wrist line, degrees from vertical (+ reaching out, − tucked in) | within ±10° |
| Spine tilt | forward bend of the hip-center → shoulder-center line from vertical | 30–45° |
| Knee bend | knee flex = 180° − the hip-knee-ankle angle (0 = straight leg) | 15–35° |
| Back rounding (hump) | how far the outline of your back bulges beyond a straight line from hip to shoulder level, from the body silhouette (MediaPipe segmentation), in body lengths | ≤ 0.06 |

**2. Swing plane (implemented).** The line through the clubhead (hosel) and
grip you click at address. Drawn in orange on the address key frame, extended
up to where it meets your body. Settings live in `[analyzers.swing_plane]`.

| Measurement | How | Good range (default) | If outside |
|---|---|---|---|
| **Points at** (key check) | where the extended shaft line crosses your torso, as a fraction of the way from hip center (0) to shoulder center (1) | 0–0.45, the belt-buckle area | **Flag**. Above: shaft too upright (standing too close / hands too high). Below: shaft too flat (too far from the ball / hands too low) |
| **Shaft angle** | angle of the line above horizontal | 45–65° | **Watch** only: it depends on the club and camera height |

Typical shaft angles by club, for reference: driver 45–50°, mid-irons 50–55°,
short irons and wedges 55–65°. The reference photo used to set these measured
53°, pointing at 0.30 of the way up the torso; Tiger and McIlroy measure 55° and
58° at 0.25.

**Notes for the checkpoints still to build:**
- **Takeaway, backswing, top and follow-through (3, 4, 5, 8)** judge where the
  **club** is. The pose model only tracks the body, so these need the club's
  position on those frames. The proposed approach is for you to click the shaft
  on each checkpoint frame in the marking screen, the same way as the ball and
  grip at address. Not decided yet.
- The app already finds takeaway, top, early downswing and impact frames
  automatically from the hand path (adjustable on the results page), so new
  checkpoints can use them.
- Drawing the hand path (wrist trail) on the video and key frames is switched
  off (`[output] show_hand_path = false`): no current check uses it, and wrist
  tracking makes it jittery. The downswing checkpoint (6) may bring it back,
  smoothed.
- The earlier down-the-line check (hands between a shaft line and a shoulder
  line at takeaway, top and early downswing) was removed when this list
  replaced it.

### Face-on (future release)

Built and unit-tested on made-up data, but not yet validated on real clips, so
it's switched off in the app (`FACE_ON_ENABLED` in `swingcheck/app/server.py`).
Swings already saved as face-on can still be opened, and switched to
down-the-line from the marking screen.

| Check | What it tells you |
|---|---|
| **Hands at impact** | Hands ahead of, level with, or behind the ball (scoop / shaft lean) |
| **Weight shift** | How far the hips moved toward the target by impact (low point / fat shots) |
| **Head drift** | Whether the head moved away from the target by impact |

### Other ideas, not planned yet

Backswing sway, vertical head movement, early extension, automatic club
detection, and trends across sessions.

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

### Face-on (for a future release)

Face-on analysis isn't available in the app yet; this is how to film it when it is.

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

1. **New swing.** Choose a down-the-line video (or drop it on the page). It
   uploads and converts with a progress bar; the conversion straightens rotated
   phone video and keeps the slo-mo frame rate. (Face-on is shown but disabled
   until a future release.)
2. **Mark your address.** Scrub to your address position with the slider, the
   ‹ › buttons or the arrow keys (Shift = 10 frames). Then click:
   - the **ball**
   - the **clubhead at the hosel**, where the shaft meets the head
   - the **grip**, the center of your hands

   A magnifier follows the cursor; on a phone, touch and hold, slide to aim with
   the magnifier above your finger, and let go to place the point. **Undo**
   removes the last point. **The frame you mark on is your address frame**:
   the address checks are measured on it, so pick a frame where you're fully set
   up and still. If a swing was saved with the wrong camera view, switch it
   under **Camera view** at the top of this screen.

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

In **Phases** on the results page, press **Adjust** next to top or impact,
scrub to the right frame, and press **Set as …**. The swing is re-analyzed with
your frame, which is remembered. **Reset to automatic** goes back to detection.
Address is the frame you marked on; change it with **Edit marks**.

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

**Address posture.** Measured on the frame you marked, using the body points on
the camera side (your trail side). Default ranges are in the [Roadmap](#roadmap).

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

**Swing plane.** The orange line on the address key frame runs along your shaft,
from the clubhead up through your hands to where it meets your body; the green
band on the torso is the belt-buckle zone it should hit. "Crosses torso at" is that
crossing as a fraction from hip (0) to shoulder (1). The shaft angle is shown
too, but only warns, since it changes with the club and camera height.

Face-on checks are described in the [Roadmap](#roadmap) (future release).

---

## Tuning

All thresholds are in [`config/default.toml`](config/default.toml), each with a
comment. **Don't edit that file.** Create `config/local.toml` (ignored by git)
with only what you want to change:

```toml
[golfer]
handedness = "right"          # or "left"

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
