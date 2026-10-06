# User guide

How to film, mark, and read your swing, in detail.

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
  Black bars baked into the picture (screen recordings, re-shared clips) are
  cropped off when the video is converted (`crop_black_bars` in `[ingest]`), and
  **About this clip** says so.
- **Same camera spot every session** (mark the tripod feet with tape). Angles
  and distances are measured in 2D, so moving the camera changes the numbers even
  when your swing doesn't.
- **Reasonably fitted clothing.** A loose shirt changes your outline, which the
  back-rounding check reads.

### Down-the-line

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

- The camera faces you, **square to the target line**.
- Center it on the **ball / your sternum**, at about **chest height**.
- For a right-hander the target is on the **right of the screen**; for a
  left-hander, the left. Choose your handedness when uploading. If your setup
  is unusual, set `target_direction_fo` explicitly.
- Distance: full body plus the club at the top in frame (often 3 to 4 m).

---

## Using the app

1. **New swing.** Choose a down-the-line video (or drop it on the page). It
   uploads and converts with a progress bar; the conversion straightens rotated
   phone video and keeps the slo-mo frame rate. It then takes a quick look
   through the clip (about 5–20 s) to find your swing, so each marking step can
   open on a **suggested frame** (address opens on the clip's first frame; the
   address found automatically, the last still frame before the hands start back,
   is used for the camera check and to find the other checkpoints; takeaway is
   where the hands have covered 12% of their path to the top, which lands within
   about a frame of the shaft being parallel; halfway back is where the hands
   have risen 45% of the way to their top height), and checks
   the camera at address. (Face-on is
   shown but disabled until a future release.) Under the camera choice, **ⓘ How to set
   up the camera** opens a guide for each view: a setup picture (the phone on a stand
   at hip height, and a side view of where it goes; from
   [OnForm](https://onform.com/blog/how-to-video-your-golf-swing-for-better-analysis/),
   credited under the picture) and four tips. The home page shows the
   down-the-line guide before your first swing (`static/setup.js`, pictures in
   `static/setup/`). Choose **Right-handed** or
   **Left-handed** under *Golfer*; the choice is remembered for next time, and a
   swing's handedness can be switched later on the marking screen (*Golfer*):
   the marks stay, and it's analyzed again. The same goes for **Club**: *Iron or
   wedge* (irons, hybrids, and wedges) or *Driver or wood* (driver and fairway
   woods), which sets a few address ranges (see [checkpoints.md](checkpoints.md)).

   **Camera check.** The marking screen opens with the result: a green "✓ a good
   down-the-line view", or what to film differently: camera off to one side or
   not behind you at all (your shoulders and hips look too wide), facing the wrong
   way for the handedness chosen (camera on the target side, or the wrong
   handedness picked), small in the frame, head or feet cut off, or
   hard to see. A red one means results would likely be wrong, so film again.
   Thresholds are in `[camera_check]` in `config/default.toml`.
2. **Mark your swing.** There are six steps, all required: address, then one
   per checkpoint. Each step tab shows its number, turning into a green ✓ once
   it's marked. **Save and analyze** unlocks once every step is marked, and
   the line under it lists what's still to mark. Each step has two parts, led by
   the dark bar above the frame (it flashes when it changes):
   1. **Drag the slider to match the example.** Rory McIlroy at the same moment sits
      beside or in the corner of your frame, with a one-line description (*Set up and still, just
      before the club moves*). Move the slider, the ‹ › buttons or the arrow keys
      (Shift = 10 frames) until your frame matches, then press **Frame looks
      right ›** (a click on the frame before that only points at the button). Each step opens on a
      suggested frame (the caption says *Suggested frame*); **Back to the
      suggested frame** returns to it.
   2. **Click the points,** one at a time, in large type with exactly where
      under it (*Click the ball*, *Center of the ball*). When the step is done,
      **Next ›** moves to the next step. The frame is locked meanwhile, so the
      clicks stay on it; **‹ Change frame** goes back to part 1 and clears the
      step's clicks.

   **Address.** Move the slider to your set-up position, then click:
   - the **club neck**, where the shaft goes into the clubhead (the hosel), not
     the clubface: the shaft line through it is your swing plane
   - your **hands**, the middle of your grip, between your two hands

   Each point has its own color: the ball a yellow ring, the club neck and clubhead
   a pink circle, your hands a blue square (the same on the example and in the
   list). A magnifier follows the cursor; on a phone, touch and hold, slide to aim with
   the magnifier above your finger, and let go to place the point. **Undo**
   (above the frame) removes the last point, and **Clear step** removes all of
   this step's points. **The frame you mark on is your address frame**:
   the address checks are measured on it, so pick a frame where you're fully set
   up and still. If a swing was saved with the wrong camera view or
   handedness, switch it under **Camera view** or **Golfer** below the marking
   panel.

   **Takeaway.** Move the slider to where the shaft is parallel to the target
   line (from behind it points at the camera), and click the **ball**, then the
   **clubhead**. That frame becomes the takeaway checkpoint. The ball is clicked
   here rather than at address because the clubhead often hides it at address;
   it doesn't move until impact and the camera is still, so it's the same spot,
   and it's saved with the address marks.

   **Halfway back.** Switch to the **Halfway back** step, move the slider to
   where your lead arm is parallel to the ground, and click the **clubhead**
   (or the highest point of the shaft you can see) and then your **hands**.

   **Top.** Switch to the **Top** step, move the slider to where the club stops
   going back, and click the **clubhead** and then your **hands**.

   **Downswing.** Switch to the **Downswing** step, move the slider to where
   the shaft is parallel to the ground coming down, and click the
   **clubhead**.

   **Follow-through.** Switch to the **Follow-through** step, move the slider
   to where your trail arm is parallel to the ground after impact, and click
   the **clubhead** and then your **hands** (or the lowest point of the shaft
   you can see, if your hands are hidden).

   **The example.** Rory McIlroy at the same moment, with that step's marks, so
   you can see what to look for and where to click (for a swing set to **Driver or
   wood**, Tiger Woods with a driver instead). On a wide screen with a
   portrait video he's beside your frame at the same size; otherwise (a phone,
   or a landscape video) he's a small picture in the top corner on the side you
   face, sized to stay clear of you: the quick pass after upload saves where you
   are in the frame (`golfer_box` in `suggest.json`). While you click, the mark of
   the point the bar asks for pulses on the example. Tap the small picture to
   enlarge it, and again to shrink it (taps on it never place a point). The
   frames ship with the app
   (`swingcheck/app/static/reference/`, and `reference/driver/` for the driver);
   rebuild them from any fully marked swing with
   `python -m swingcheck.app.make_reference runs/<swing-folder> "Name"` (add
   `driver` at the end for the driver example).

   **Mark checks.** Marks that look wrong get a yellow note under the frame and
   a **!** on the step: hands below the club neck at address, the club neck far
   from the ball, the clubhead below your hands at halfway back or the
   follow-through, a step whose frame comes before the previous one, or a
   clubhead much too far from your hands. The ones that can't be right (a frame
   out of order, or the clubhead and hands clicked the wrong way round) block
   **Save and analyze**, which says what to fix and opens that step; the rougher
   distance checks only ask once whether to go ahead.

   **Trim the clip** (below the points) cuts out practice swings or idle time:
   move the slider to a frame, press **Start here** or **End here**, then **Apply trim**.
   Your points are kept.
3. **Save and analyze.** Saving your marks starts the analysis straight away.
   Tracking your body takes about a minute for a few seconds of 240 fps slo-mo
   on a laptop, with live progress. You can leave the page and come back.
4. **Results.** The annotated video (with 0.25× and 0.5× speeds) on one side;
   on the other, the **checkpoints**: a strip of the eight down-the-line
   checkpoints in swing order, each colored by its result (dashed = coming
   soon). It opens on the checkpoint to work on first. Pick another, or use ‹ ›
   / the arrow keys, to see its key frame (drawn with only that check's lines)
   next to its card. Each card lists its measurements one per row with a status
   dot, with the biggest issue highlighted. **Impact frame** (collapsed) lets
   you fix the impact frame, and **Text report** opens a plain-text summary.

Your swings are listed on the home page, newest first, with their verdicts. Open
one to see it again, **Edit marks** to re-mark, **Re-analyze** after changing
settings, or **Delete** to remove it and its files.

### When the impact frame is wrong

Impact is the one checkpoint found automatically. If its frame is off, open
**Impact frame** on the results page, press **Adjust impact**, move the slider to the
right frame, and press **Set as impact**. The swing is re-analyzed with your
frame, which is remembered. **Reset to automatic** goes back to detection. Every
other checkpoint uses the frame you marked; change those with **Edit marks**.
Impact has to come after the top you marked: an earlier frame is refused, with a
note saying so.

### Where your swings are stored

Each swing is a folder in `runs/` in the project. It holds the original upload,
the converted video, your marks, the analysis, `annotated.mp4` (saved 720 px wide
to stay quick to load), the full-size key frame images and `report.txt`. The page
shows small JPEG copies of the key frames (`*.w720.jpg`, `*.w360.jpg`, made on first
view). Clicking a key frame shows it large over the page (tap anywhere or Close to go back);
Ctrl/Cmd-click opens the full-size PNG in a new tab. Back up or delete that folder like any other files.
