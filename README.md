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
| 3 | **Takeaway** | When the club is parallel to the target line in the takeaway, the clubhead is still on the address shaft line (on plane) | ✅ Implemented |
| 4 | **Backswing (halfway back)** | At lead arm parallel, the shaft points back at or just inside the golf ball ("hands split the biceps" was tried and dropped) | ✅ Implemented |
| 5 | **Top of backswing** | The lead (left) arm matches the shoulders, 90° to the spine (hands-on-plane was tried and dropped) | ✅ Implemented |
| 6 | **Downswing** | With the shaft parallel to the ground coming down, the club is back on plane and flatter than at the takeaway (shallowing) | ✅ Implemented |
| 7 | **Impact** | The hips stay back on the "tush line" (no early extension) and the spine bend is kept | ✅ Implemented |
| 8 | **Follow-through** | With the trail arm parallel after impact, the club exits on plane, on the same line as at halfway back | ✅ Implemented |

**What "plane" means here.** The **swing plane line** is the one from
checkpoint 2: your shaft at address (clubhead through grip), extended so it
points at your belt buckle. It's drawn in orange and is the only line called
"swing plane". Takeaway (3) and downswing (6) check that the **clubhead** stays
on or near it. Halfway back (4) and follow-through (8) check where the shaft
itself points at the ball's level. The top (5) checks the lead arm against the
spine.

The swing plane line is drawn across the whole frame, with a grey boundary
line either side marking the on-plane corridor (±20% of torso length, about
±10 cm: the takeaway's green band, `line_tolerance`), on every checkpoint's key
frame from 2 to 8, and it stays on screen for the whole annotated video, so you
can follow the clubhead against it through the swing by eye.

**Colors and units.** Every measurement is graded 🟢 green (good), 🟡 yellow
(watch: just outside good) or 🔴 red (flag), and a checkpoint takes the worst
color of its measurements. Angles are in degrees. Distances are measured as a
**percent of your torso length** (hip center to shoulder center at address),
so they don't depend on how far the camera is; the card also shows rough
centimetres using `[golfer] torso_cm` (50 cm by default; set your own for
accurate cm).

**1. Address / alignment (implemented).** Measured on the frame you mark on,
which is the address frame for down-the-line, using the body points on the
camera side (your trail side). Settings live in `[analyzers.address]` in
`config/default.toml`.

| Measurement | How | 🟢 Green | 🟡 Yellow | 🔴 Red |
|---|---|---|---|---|
| Arms hang straight down | shoulder → wrist line, degrees from vertical (+ reaching out, − tucked in) | within ±10° | 10–15° | past 15° |
| Spine tilt | forward bend of the hip-center → shoulder-center line from vertical | 30–45° | 25–30° or 45–50° | below 25° or above 50° |
| Knee bend | knee flex = 180° − the hip-knee-ankle angle (0° = straight leg) | 15–35° | 10–15° or 35–40° | below 10° or above 40° |
| Back rounding (hump) | how far the outline of your back bulges beyond a straight line from hip to shoulder level, from the body silhouette (MediaPipe segmentation), as % of torso length | up to 6% (≈3 cm) | 6–9% | past 9% (≈4.5 cm) |

When something is out of range, the card says how far and which way to move,
rounded up so following it lands you in green (e.g. *Spine bend 28.8° — bend
2° more (green 30–45°, red outside 25–50°)*), and the summary gives a plain
fix, leading with the hips:
standing tall with straight knees and reaching arms usually comes from too
little hip hinge. The key frame adds a dashed green **aim** line for each
yellow or red part at the middle of its green range: the spine at 37.5°, the arm straight
down, and the thigh at 25° of knee flex (shin kept where it is).

**2. Swing plane (implemented).** The line through the clubhead (hosel) and
grip you click at address. Drawn in orange across the whole frame (and the
whole video), with the belt-buckle zone in green on your torso and where the
line crosses it. Settings live in `[analyzers.swing_plane]`.

| Measurement | How | 🟢 Green | 🟡 Yellow | 🔴 Red |
|---|---|---|---|---|
| **Alignment** (key check) | where the extended shaft line crosses your torso, as % of the way from hip center (0%) to shoulder center (100%) | 0–45%: **Points at belt buckle** | −10–0%: *just below belt*; 45–60%: *just above belt* | below −10%: **Points below belt** (shaft too flat: too far from the ball / hands too low); above 60%: **Points above belt** (too upright: too close / hands too high) |
| **Shaft angle** | angle of the line above horizontal | 45–65° | 40–45° or 65–70° | below 40° or above 70° (check the club and camera height) |

Typical shaft angles by club, for reference: driver 45–50°, mid-irons 50–55°,
short irons and wedges 55–65°. The reference photo used to set these measured
53°, pointing 30% of the way up the torso; Tiger and McIlroy measure 55° and
58° at 25%.

**3. Takeaway (implemented).** On the **Takeaway** step of the marking screen,
you scrub to where the shaft is parallel to the target line (from behind it
points at the camera) and click the clubhead and your hands; that frame is the
takeaway checkpoint. Settings live in `[analyzers.takeaway]`.

| Measurement | How | 🟢 Green | 🟡 Yellow | 🔴 Red |
|---|---|---|---|---|
| **Clubhead vs swing plane** | distance of the clubhead from the swing plane line (checkpoint 2's line), square to it, as % of torso length | within ±20% (≈10 cm): **Club on plane** | 20–50%: *slightly inside / outside the swing plane* | past 50% (≈25 cm): *well inside* (your side: pulled inside or rolled open) or *well outside* (ball side: picked up outside) |
| **Spine bend kept** | spine bend (hip center → shoulder center, from vertical) on the takeaway frame vs address, from tracking | up to 6° more upright or 5° more bent: **posture kept** | 6–10° more upright (*slightly standing up*) or 5–10° more bent (*slightly bending over*) | more than 10°: **standing up** early or **bending over** |
| **Trail knee flex kept** | trail knee flex (180° − hip-knee-ankle angle) on the takeaway frame vs address, from tracking | up to 5° straighter or 8° more bent: **flex kept** | 5–10° straighter (*slightly straightening*) or 8–15° more bent (*slightly sinking*) | more than 10° straighter: trail leg **straightening** (locking out); more than 15° more bent: **sinking** |

The card shows the worst of the three. References: McIlroy loses 2° of spine
bend and 3° of knee flex, Tiger 5.5° and gains 2°, all green. If a body point
isn't tracked, that row says "not measured" and the others decide.

Where your hands are doesn't matter for this check. The rule started as "the
club covers the hands", but that depends on where the hands went, and the
clubhead staying on the address shaft line is the cleaner on-plane test.

Good players vary here, which is why the yellow band is wide: McIlroy reads 4%
outside (on plane); Tiger 38% inside on one clip and 21% outside on another;
Morikawa by eye goes back with the clubhead outside his hands; an amateur swing
taken away low and inside reads 50%, right at the red line. Camera aim also
matters: the clubhead is about a metre closer to the camera than at address,
so a camera pointed 5° off the target line moves it sideways by about 18% of
torso length. The thresholds (`line_tolerance`, `flag_distance`) are a first
guess from these few swings; tune them as more clips come in.

The key frame shows the address shaft line (orange) with the on-plane band
either side (grey), a tick from the clubhead square to the line, and the hands
for reference. If the takeaway isn't marked, this checkpoint says so instead of
guessing.

**4. Halfway back (implemented).** On the **Halfway back** step of the marking
screen, scrub to where your **lead arm is parallel to the ground** (hands about
level with your lead shoulder) and click the **clubhead** (or the highest point
of the shaft you can see, if the clubhead is out of frame) and your **hands**.
Settings live in `[analyzers.halfway_back]`.

| Measurement | How | 🟢 Green | 🟡 Yellow | 🔴 Red |
|---|---|---|---|---|
| **Shaft points** | the line from the clubhead through the hands, carried down to the ball's level: where it lands vs the ball, as % of torso length | 10% past the ball to 40% inside (between the ball and your feet): **Points at the ball** / **just inside the ball** | 40–70% inside (*a little steep*) or 10–25% past the ball (*a little flat*) | past 70% inside: **Points at your feet** (too steep / upright); more than 25% past the ball: **Points outside the ball** (too flat / laid off) |

Set from a reference photo (a scratch golfer: shaft 26% inside the ball,
green). McIlroy at lead arm parallel reads 30% inside (green); an amateur swing
that went back inside at the takeaway reads 117% past the ball (laid off, red).
Your spec also asked for "the hands split the biceps"; that check was built and
then dropped: from behind, the trail elbow is half hidden at this point, so the
tracked biceps line moved too much to judge a few centimetres reliably.

The key frame shows the shaft line (green) carried down to the ball's level and
a tick from where it lands to the ball.

**5. Top (implemented).** On the **Top** marking step, scrub to the top of your
backswing (the moment the club stops going back) and click the **clubhead** and
your **hands**. Body points come from tracking. Settings live in
`[analyzers.top]`.

| Measurement | How | 🟢 Green | 🟡 Yellow | 🔴 Red |
|---|---|---|---|---|
| **Lead arm vs spine** | angle between the lead arm (lead shoulder → hands) and the spine, drawn from the hip center through the head, on the top frame; 90° = the arm matches the shoulders | 75–105°: **Lead arm matches the shoulders** | 65–75° (*slightly above*) or 105–115° (*slightly below*) | under 65°: arm lifted **above the shoulders** (upright); over 115°: **below the shoulders** (flat, around the body) |
| **Hands vs trail heel** | how far the hands sit across the picture from straight above the trail heel (tracked, median of a few frames around the top), as % of torso length; drawn as a dashed plumb line up from the heel | within ±15% (about 7 cm): **Hands over the trail heel** | 15–30% (*slightly outside* / *slightly behind the heel*) | more than 30%: hands **outside the heel** (out toward the ball) or **behind the heel** (deep, flat) |

The card shows the worse of the two. References for the hands: McIlroy about
2 cm toward the ball, Tiger about 6 cm, both green. If the heel isn't tracked,
that row says "not measured" and the arm decides.

The spine runs from the hips **through the head**, the way golf instruction
draws the spine angle (it matched the coach's spine marker on the reference
photo within a few degrees). A line to the middle of the shoulders came out too
upright at the top, because the turned shoulders' midpoint slides across the
upper back: Tiger read 70° that way although his arm is visibly about square to
his spine. Seen from behind the lead arm points partly at the camera, so green
is 75–105°. Readings: McIlroy 91°, Tiger 77° (green); an amateur swing 73°
(slightly lifted, yellow). A "hands in the plane zone" check (hands between the
swing plane line and a shoulder plane) was tried here and dropped. The key
frame shows the spine (white), the lead arm in its color, and a dashed green
line square to the spine where the arm should be.

**6. Downswing (implemented).** On the **Downswing** marking step, scrub to
where the **shaft is parallel to the ground on the way down** (P6, hands about
hip height; the mirror of the takeaway) and click the **clubhead** and your
**hands**. Settings live in `[analyzers.downswing]`.

| Measurement | How | 🟢 Green | 🟡 Yellow | 🔴 Red |
|---|---|---|---|---|
| **Clubhead vs swing plane** | the clubhead's distance from the swing plane line, square to it (as at the takeaway), as % of torso length | on the line to 40% under (behind the hands): **Club down the swing plane** | up to 30% above (*slightly steep*; a little above is forgivable) or 40–70% under (*well under*) | more than 30% above (≈15 cm): **over the top**; more than 70% under: **stuck** (too flat) |
| **Shallowing** | that distance minus the same one at your takeaway: + = the club comes down flatter than it went back | 0% or more flatter: **Shallowed** | up to 20% steeper | more than 20% steeper than going back: the over-the-top loop |

Why compare with the takeaway and not shaft angles: at P6, like at the
takeaway, the shaft points roughly at the camera, so its angle on screen is
unreliable, but the clubhead's position against the address shaft line is
not. Shallowing needs the takeaway marked; without it the card shows the
plane check only. No reference photo for this one: the bands are from
standard teaching, checked on McIlroy (13% under the line, 17% flatter than
his takeaway: green) and an amateur swing (back inside at 50%, then about on
the line coming down: 28% *steeper* than going back, the classic loop, red).
In dim, low-frame-rate footage the clubhead can be a streak and the exact P6
frame can be missing; pick the nearest frame.

**7. Impact (implemented).** Automatic, on the detected impact frame (adjust it
under **Phases** on the results page if it's off); no extra marks. Settings live
in `[analyzers.impact]`. No reference photo: defined from the two classic
down-the-line impact checks.

| Measurement | How | 🟢 Green | 🟡 Yellow | 🔴 Red |
|---|---|---|---|---|
| **Hips vs tush line** | the rear edge of your body outline at hip height (from segmentation), at impact vs address, as % of torso length | moved back, or up to 10% (≈5 cm) toward the ball: **Hips on the tush line** | 10–15% toward the ball | more than 15% (≈7.5 cm, about 3 in): **Early extension** (hips thrust toward the ball) |
| **Spine bend kept** | forward bend of the hip-center → shoulder-center line at impact vs address | up to 10° more upright or 6° more bent: **Posture kept** | 10–15° more upright (*slightly standing up*) or 6–12° more bent (*slightly dipping*) | more than that: **Standing up** / **Dipping** |

Good players lose a few degrees of bend as the hips open (McIlroy about 7°)
and often move the hips a few cm toward the ball, so the bands leave room for
that. Readings: McIlroy 8% toward the ball and 7° more upright; Tiger 4–15%
*back* and 2–3° more bent (all green); an amateur swing 18% (≈9 cm) toward the
ball: early extension, red. The key frame shows the address tush line (white),
where the rear of the hips is at impact, and the spine now (colored) vs at
address (dashed).

**8. Follow-through (implemented).** On the **Follow-through** marking step,
scrub to where your **trail arm is parallel to the ground after impact** (hands
about shoulder height: the mirror of halfway back) and click the **clubhead**
and your **hands**. From behind, the hands are often hidden behind your body
here: click the lowest point of the shaft you can see instead (any two points
on the shaft define its line), and if the arms are hidden, pick the frame
where the shaft looks about as steep as at halfway back. Settings live in
`[analyzers.follow_through]`.

| Measurement | How | 🟢 Green | 🟡 Yellow | 🔴 Red |
|---|---|---|---|---|
| **Shaft points** | the shaft line carried down to the ball's level, as at halfway back | 15% past the ball to 60% inside: **Exits on plane** | to 30% past (*slightly flat*) or 60–85% inside (*slightly steep*) | beyond: **Exits flat** / **Exits steep** |
| **Same line as backswing** | this landing vs the halfway-back landing, as % of torso length | within ±30%: **Same line as the backswing** | 30–55% apart (*slightly steeper / flatter*) | more than 55% apart |

Set from the same reference golfer (follow-through on the ball, halfway back
16–26% inside: about 20% apart, green). McIlroy exits 48% inside, 18% steeper
than his halfway back (green); an amateur swing exits on the ball but its
halfway back was laid off 117% past the ball, so the exit is 117% steeper than
the way back (red). Same-line needs halfway back marked; otherwise only the
shaft row. The key frame shows the shaft line carried to the ball's level and
where the halfway-back line landed (grey), joined by a tick.

**Notes:**
- Each club-based checkpoint (3, 4, 5, 6, 8) has a marking step where you
  pick the frame and click the clubhead and hands (stored in `marks.json`
  under `checkpoints`), because the pose model only tracks the body. Address
  and impact use the detected frames (adjustable on the results page).
- Drawing the hand path (wrist trail) on the video and key frames is switched
  off (`[output] show_hand_path = false`): no current check uses it, and wrist
  tracking makes it jittery.
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
  warns if a clip is 60 fps or slower. A shared copy is easy to spot: a
  2-second swing comes through as a 10+ second video, because the slow-motion
  part was baked in for playback. Such copies also often have frames missing;
  the app keeps every frame that's there and repeats the previous one over a gap.
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

   **Takeaway (optional).** Switch to the **Takeaway** step, scrub to where the
   shaft is parallel to the target line (from behind it points at the camera),
   and click the **clubhead** and then your **hands**. That frame becomes the
   takeaway checkpoint. It starts near the automatically detected takeaway.

   **Halfway back (optional).** Switch to the **Halfway back** step, scrub to
   where your lead arm is parallel to the ground, and click the **clubhead**
   (or the highest point of the shaft you can see) and then your **hands**.

   **Top (optional).** Switch to the **Top** step (it starts on the detected
   top), scrub to where the club stops going back, and click the **clubhead**
   and then your **hands**.

   **Downswing (optional).** Switch to the **Downswing** step, scrub to where
   the shaft is parallel to the ground coming down, and click the
   **clubhead** and then your **hands**.

   **Follow-through (optional).** Switch to the **Follow-through** step, scrub
   to where your trail arm is parallel to the ground after impact, and click
   the **clubhead** and then your **hands** (or the lowest point of the shaft
   you can see, if your hands are hidden).

   **Trim the clip** (below the points) cuts out practice swings or idle time:
   scrub to a frame, press **Start here** or **End here**, then **Apply trim**.
   Your points are kept.
3. **Analyze.** Tracking your body takes about a minute for a few seconds of
   240 fps slo-mo on a laptop, with live progress. You can leave the page and
   come back.
4. **Results.** The annotated video (with 0.25× and 0.5× speeds) on one side;
   on the other, the **checkpoints**: a strip of the eight down-the-line
   checkpoints in swing order, each colored by its result (dashed = coming
   soon). Pick one, or use ‹ › / the arrow keys, to see its key frame (drawn with
   only that check's lines) next to its card. Each card lists its measurements
   one per row with a status dot. **Phases** (collapsed) lets you fix a frame,
   and **Report** opens a plain-text summary.

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

The results page opens with a **swing summary**: one numbered dot per
checkpoint (green, yellow, red; dashed = not measured yet), how many are good /
to watch / to fix, and **Work on first**: the first red checkpoint in swing
order (or the first yellow) with a one-line fix. Tap a dot to jump to that
checkpoint. Below it, the checkpoints go one at a time (‹ › or the arrow keys):
the checkpoint's key frame next to its card, which gives the result, what it
means, **How to fix** when it's yellow or red, and each measurement with its
limits. The annotated video and the detected phases sit beside it on a wide
screen and below it on a phone. **Re-analyze** is the main button; **Download
summary** saves a PDF to share outside the app (scorecard, the one thing to work
on first, then each checkpoint's key frame, readings with their limits, and how
to fix), built from the last analysis; **Edit marks**, the text report and
**Delete** are in the ⋯ menu. In the annotated video, the
header names only the checkpoint whose lines are on screen.

On the swing list, each analyzed swing shows the same 8 dots under its
thumbnail; swings still to mark or analyze say what's next.

Every measurement is 🟢 **OK**, 🟡 **Watch** (just outside good, worth a look)
or 🔴 **Flag**, and each card row says the green and red limits it was judged
against. Angles are in degrees. Distances are a **percent of your torso
length** (hip center to shoulder center, measured at address), so `10%` means a
tenth of your torso whatever the camera distance; the card adds rough cm
(`≈5 cm`) from `[golfer] torso_cm` in the config (50 cm unless you set yours).

**Address posture.** Measured on the frame you marked, using the body points on
the camera side (your trail side). Default ranges are in the [Roadmap](#roadmap).

- **Arms:** the shoulder-to-wrist line should hang straight down. Reported in
  degrees from vertical; + means the hands reach out toward the ball, - means
  they're tucked in toward the body.
- **Spine:** forward bend of the hip-to-shoulder line from vertical.
- **Knees:** knee flex, 0 = straight leg.
- **Back:** how far the outline of your back bulges beyond a straight line
  between hip and shoulder level (% of torso length), measured from the body
  silhouette. A rounded upper back (hump) reads higher.

The address key frame draws each line with its value in its color (green,
yellow or red), plus dashed green aim lines for anything not green.

**Swing plane.** The orange line on the address key frame runs along your shaft,
from the clubhead up through your hands to where it meets your body; the green
band on the torso is the belt-buckle zone it should hit. **Alignment** says
whether it points at the belt buckle, above or below the belt, and what that
means; the value is how far up the torso it crosses (0% = hip center, 100% =
shoulder center). The shaft angle has a broad range, since it changes with
the club and camera height.

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
| "Can't reach the swing-check app" or "The app was restarted while this was running" | The app stopped (its terminal was closed or it was restarted) during a conversion or analysis. Analysis runs inside the app, so closing it stops the job. Start `swingcheck` again and press **Try again**. |
| Address checks measured on the wrong frame | **Edit marks**, scrub to your set-up position, and save again. |
| Back reads rounded but isn't | Loose clothing changes the outline; check the line drawn on the address key frame. |
| Wrong top/impact | **Adjust** it under Phases on the results page. |
| A check says "No data" | A body point wasn't tracked at that moment: usually lighting, part of the body out of frame, or baggy clothing. |
| Practice swing detected instead of the real one | **Edit marks** → **Trim the clip**. |
| Page looks broken after updating the code | Reload the page (Ctrl+R). |

---

## Adding a check

Checks are plug-ins. To build one of the down-the-line checkpoints, create a
file in `swingcheck/analyzers/` that registers an analyzer under the **name and
phase listed for that checkpoint in `swingcheck/checkpoints.py`**. It's picked
up automatically and appears in the app's checkpoint stepper; nothing else
needs to change. An illustration (not the real top-of-backswing check):

```python
# swingcheck/analyzers/dtl_top.py
from swingcheck.analyzers import STATUS_COLORS, Overlay, Row, SwingContext, Verdict, register
from swingcheck.geometry import angle_between_deg

@register("top", view="dtl", title="Top", phase="top")  # name and phase from checkpoints.py
def top(ctx: SwingContext) -> Verdict:
    f = ctx.frame("top")
    shoulder = ctx.value(ctx.track(ctx.side("shoulder", "lead")), f, "lead shoulder")
    wrist = ctx.value(ctx.track(ctx.side("wrist", "lead")), f, "lead wrist")
    hip = ctx.value(ctx.track(ctx.side("hip", "lead")), f, "lead hip")
    angle = angle_between_deg(wrist - shoulder, hip - shoulder)
    ok = abs(angle - 90) <= ctx.cfg["tolerance"]  # from [analyzers.top] in the config
    status = "ok" if ok else "flag"
    return Verdict(
        status=status,
        label="lead arm square to the torso" if ok else "lead arm off 90°",
        summary=f"Lead arm is {angle:.0f}° from the torso at the top.",
        measurements={"lead_arm_to_torso_deg": round(angle, 1)},          # for the report
        rows=[Row("Lead arm to torso", f"{angle:.0f}°", "good" if ok else "off 90°", status)],  # for the card
        overlays=[Overlay("segment", [tuple(shoulder), tuple(wrist)], STATUS_COLORS[status], frames=(f, f))],
    )
```

Then add its settings under `[analyzers.top]` in `config/default.toml`, mark it
✅ in the [Roadmap](#roadmap), and update the expected list in
`tests/test_app.py::test_checkpoint_list_marks_built_ones`.

The context gives you the pose (`ctx.track(name)` for any MediaPipe landmark,
`ctx.hands()`, `ctx.midpoint(a, b)`), your marks (`ctx.marks.points`), phase
frames (`ctx.frame("top")`, `ctx.at(track, "impact")`, `ctx.value(track, frame,
what)`), lead/trail sides (`ctx.side("shoulder", "trail")`), the video frame
(`ctx.image(frame)`), and body-unit conversion (`ctx.units(px)`).
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
