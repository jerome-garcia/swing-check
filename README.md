# SwingCheck

**Alpha:** features, results and limits may still change. The app says so with a
badge in the header, a footer line and the Terms.

A golf swing analyzer that runs on your own computer. Upload a **down-the-line**
video of one swing, click the ball and club, and it gives you an annotated
video, key frames and a verdict for each check. Open it in your browser on the
PC, or on your phone over Wi-Fi.

The goal is to fix fat shots, scooping, and wedges/hybrids flying high instead
of far. The down-the-line analysis is being built as **eight checkpoints**
through the swing; see [Roadmap](#roadmap) for what each one checks and which
are done. **Face-on** analysis is held back for a future release.

It's built with Python, OpenCV, MediaPipe Pose and ffmpeg. Run on your own
computer, everything stays there and nothing is uploaded anywhere. The online
version (hosted mode, below) keeps each video on the server for 3 days; the app's
Terms of use and Privacy notice pages explain it.

### Support SwingCheck

SwingCheck is free. If it helps your game, you can
[support it on Ko-fi](https://ko-fi.com/jeromegarcia) to help cover the server
and upkeep costs. Thank you!

[![Support me on Ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/jeromegarcia)

In the Philippines? Support with InstaPay: scan this with GCash, Maya or your bank app.

<img src="swingcheck/app/static/support/instapay-qr.png" alt="InstaPay QR code" width="200">

### Brand

The one-page brand guide (logo, versions, clear space, colors, type, voice) is
[branding/swingcheck-brand-guide.pdf](branding/swingcheck-brand-guide.pdf).
The `branding/` folder also holds the logo SVGs and the Ko-fi cover. The guide and
the cover are built from HTML files there; edit one and re-render with `sh branding/render.sh`.

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
points at your belt buckle. It's drawn in magenta and is the only line called
"swing plane". Takeaway (3) and downswing (6) check that the **clubhead** stays
on or near it. Halfway back (4) and follow-through (8) check where the shaft
itself points at the ball's level. The top (5) checks the lead arm against the
spine.

The swing plane line is drawn across the whole frame, with a grey boundary
line either side marking the on-plane corridor (±20% of torso length, about
±10 cm: the takeaway's green band, `line_tolerance`), on every checkpoint's key
frame from 2 to 8, and it stays on screen for the whole annotated video, so you
can follow the clubhead against it through the swing by eye.

**Colors and units.** Every measurement is graded 🟢 green (Good), 🟡 yellow
(Watch: just outside good) or 🔴 red (Fix), and a checkpoint takes the worst
color of its measurements. Angles are in degrees. Distances are set as a
**percent of your torso length** (hip center to shoulder center at address),
so they don't depend on how far the camera is.

In the app, cards and key frames show those distances as rough
**centimetres**, scaled from `[golfer] torso_cm` (50 by default, so 10% ≈ 5 cm;
set your own for more accurate cm). They use plain words first: *front* and
*back* for lead and trail, *toward you* and *toward the ball* for inside and
outside. Each measurement lists its **Good** range and its **Fix** range;
anything in between is **Watch**. The tables below give the settings in % of
torso length, as the config file does.

**1. Address / alignment (implemented).** Measured on the frame you mark on,
which is the address frame for down-the-line, using the body points on the
camera side (your trail side). Settings live in `[analyzers.address]` in
`config/default.toml`.

| Measurement | How | 🟢 Green | 🟡 Yellow | 🔴 Red |
|---|---|---|---|---|
| Arms hang straight down | shoulder → wrist line, degrees from vertical (+ reaching out, − tucked in) | within ±10° | 10–15° | past 15° |
| Spine tilt | forward bend of the hip-center → shoulder-center line from vertical | 30–45° | 25–30° or 45–50° | below 25° or above 50° |
| Knee bend | knee flex = 180° − the hip-knee-ankle angle (0° = straight leg) | 15–35° | 10–15° or 35–40° | below 10° or above 40° |
| Upper back (rounding) | how far the outline of your back bulges beyond a straight line from hip to shoulder level, from the body silhouette (MediaPipe segmentation), as % of torso length | up to 6% (≈3 cm) | 6–9% | past 9% (≈4.5 cm) |

When something is out of range, the card says how far and which way to move,
rounded up so following it lands you in green (e.g. *Spine bend 29°: Bend 2°
more*, with *Good 30–45°* and *Fix under 25° or over 50°* below it), and the
summary gives a plain fix, leading with the hips:
standing tall with straight knees and reaching arms usually comes from too
little hip hinge. The key frame adds a dashed white **aim** line for each
yellow or red part at the middle of its green range: the spine at 37.5°, the arm straight
down, and the thigh at 25° of knee flex (shin kept where it is).

**2. Swing plane (implemented).** The line through the clubhead (hosel) and
grip you click at address. Drawn in magenta across the whole frame (and the
whole video), with the belt-buckle zone in green on your torso and where the
line crosses it. Settings live in `[analyzers.swing_plane]`.

| Measurement | How | 🟢 Green | 🟡 Yellow | 🔴 Red |
|---|---|---|---|---|
| **Shaft points at** (key check) | where the extended shaft line crosses your torso, as % of the way from hip center (0%) to shoulder center (100%) | 0–45%: **Points at your belt buckle** | −10–0%: *just below your belt*; 45–60%: *just above your belt* | below −10%: **Points below your belt** (shaft too flat: too far from the ball / hands too low); above 60%: **Points above your belt** (too upright: too close / hands too high) |
| **Shaft angle** | angle of the line above horizontal | 45–65° | 40–45° or 65–70° | below 40° or above 70° (check the club and camera height) |

Typical shaft angles by club, for reference: driver 45–50°, mid-irons 50–55°,
short irons and wedges 55–65°. The reference photo used to set these measured
53°, pointing 30% of the way up the torso; Tiger and McIlroy measure 55° and
58° at 25%.

**3. Takeaway (implemented).** On the **Takeaway** step of the marking screen,
you move the slider to where the shaft is parallel to the target line (from behind it
points at the camera) and click the clubhead (only the clubhead: the hands
don't matter here); that frame is the takeaway checkpoint. Settings live in `[analyzers.takeaway]`.

| Measurement | How | 🟢 Green | 🟡 Yellow | 🔴 Red |
|---|---|---|---|---|
| **Clubhead vs swing plane** | distance of the clubhead from the swing plane line (checkpoint 2's line), square to it, as % of torso length | within ±20% (≈10 cm): **Clubhead on the swing plane** | 20–50%: *clubhead slightly toward you / toward the ball* | past 50% (≈25 cm): *clubhead too far toward you* (pulled inside or rolled open) or *too far toward the ball* (picked up outside) |
| **Spine bend kept** | spine bend (hip center → shoulder center, from vertical) on the takeaway frame vs address, from tracking | up to 6° more upright or 5° more bent: **posture kept** | 6–10° more upright (*slightly standing up*) or 5–10° more bent (*slightly bending over*) | more than 10°: **standing up** early or **bending over** |
| **Back knee bend kept** | trail knee flex (180° − hip-knee-ankle angle) on the takeaway frame vs address, from tracking | up to 5° straighter or 8° more bent: **flex kept** | more than 5° straighter (*slightly straightening*; past 10°, *straightening*) or more than 8° more bent (*sinking*) | never: a watch item (see below) |

The card shows the worst of the three. References: McIlroy loses 2° of spine
bend and 3° of knee flex, Tiger 5.5° and gains 2°, all green. The trail knee is
yellow at most, never red: an early-straightening trail leg makes it easier to
lose posture, but it rarely costs a shot by itself, and the knee angle seen from
behind gets rough once the hips turn. So it never becomes "Work on first" ahead
of the faults that do cost shots (over the top, early extension). If a body point
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

The key frame shows the address shaft line (magenta) with the on-plane band
either side (grey), a tick from the clubhead square to the line, and the hands
for reference. If the takeaway isn't marked, this checkpoint says so instead of
guessing.

**4. Halfway back (implemented).** On the **Halfway back** step of the marking
screen, move the slider to where your **lead arm is parallel to the ground** (hands about
level with your lead shoulder) and click the **clubhead** (or the highest point
of the shaft you can see, if the clubhead is out of frame) and your **hands**.
Settings live in `[analyzers.halfway_back]`.

| Measurement | How | 🟢 Green | 🟡 Yellow | 🔴 Red |
|---|---|---|---|---|
| **Shaft points at** | the line from the clubhead through the hands, carried down to the ball's level: where it lands vs the ball, as % of torso length | 10% past the ball to 40% inside (between the ball and your feet): **Points at the ball** | 40–70% inside (*points between the ball and your feet*: a little steep) or 10–25% past the ball (*points just past the ball*: a little flat) | past 70% inside: **Points at your feet** (too steep / upright); more than 25% past the ball: **Points well past the ball** (too flat / laid off) |
| **Spine bend kept** | as at the takeaway: spine bend on this frame vs address, from tracking | up to 8° more upright or 5° more bent | 8–12° more upright (*slightly standing up*) or 5–10° more bent | more than 12° more upright: **standing up**; more than 10° more bent: **bending over** |
| **Back knee bend kept** | as at the takeaway: trail knee flex on this frame vs address | up to 6° straighter or 8° more bent | more than 6° straighter (*slightly straightening*; past 10°, *straightening*) or more than 8° more bent | never: a watch item |

The card shows the worst of the three. Good players lose only a few degrees of
either by here (McIlroy about 4° and 4°, Tiger 6° and 2°); most of the trail
knee's straightening comes later, between halfway back and the top (McIlroy's
goes from 27° at address to 15° at the top), and it never locks.

Set from a reference photo (a scratch golfer: shaft 26% inside the ball,
green). McIlroy at lead arm parallel reads 30% inside (green); an amateur swing
that went back inside at the takeaway reads 117% past the ball (laid off, red).
Your spec also asked for "the hands split the biceps"; that check was built and
then dropped: from behind, the trail elbow is half hidden at this point, so the
tracked biceps line moved too much to judge a few centimetres reliably.

The key frame shows the shaft line, in its result color, carried down to the
ball's level, and a tick from where it lands to the ball.

**5. Top (implemented).** On the **Top** marking step, move the slider to the top of your
backswing (the moment the club stops going back) and click the **clubhead** and
your **hands**. Body points come from tracking. Settings live in
`[analyzers.top]`.

| Measurement | How | 🟢 Green | 🟡 Yellow | 🔴 Red |
|---|---|---|---|---|
| **Front arm vs spine** | angle between the lead arm (lead shoulder → hands) and the spine, drawn from the hip center through the head, on the top frame; 90° = the arm matches the shoulders | 75–105°: **Front arm matches your shoulders** | 65–75° (*slightly above*) or 105–115° (*slightly below*) | under 65°: arm lifted **above the shoulders** (upright); over 115°: **below the shoulders** (flat, around the body) |
| **Hands vs back heel** | how far the hands sit across the picture from straight above the back (trail) heel (tracked, median of a few frames around the top), as % of torso length; drawn as a dashed plumb line up from the heel | within ±15% (about 7 cm): **Hands over your back heel** | 15–30% (*hands slightly toward the ball* / *slightly behind your back heel*) | more than 30%: **hands too far toward the ball** or **behind your back heel** (deep, flat) |
| **Spine bend kept** | as at the takeaway and halfway back: spine bend on the top frame vs address, from tracking; its lines are drawn only when it's off (the frame already has a spine line) | up to 8° more upright or 5° more bent | 8–12° more upright (*slightly standing up*) or 5–10° more bent | more than 12° more upright: **standing up** in the backswing; more than 10° more bent: **bending over** |

The card shows the worst of the three. References for the hands: McIlroy about
2 cm toward the ball, Tiger about 6 cm, both green. If the heel isn't tracked,
that row says "not measured" and the others decide. Spine bend at the top:
McIlroy 37° (address 37°), Tiger 30° (address 34°), both green.

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

**6. Downswing (implemented).** On the **Downswing** marking step, move the slider to
where the **shaft is parallel to the ground on the way down** (P6, hands about
hip height; the mirror of the takeaway) and click the **clubhead** (only the
clubhead: neither measurement uses the hands). On the key frame a dashed line
joins the clubhead at the takeaway to the clubhead here, to show how far it
moved. Settings live in `[analyzers.downswing]`.

| Measurement | How | 🟢 Green | 🟡 Yellow | 🔴 Red |
|---|---|---|---|---|
| **Clubhead vs swing plane** | the clubhead's distance from the swing plane line, square to it (as at the takeaway), as % of torso length | 10% above (≈5 cm: on the line, give or take a click; Tiger reads 1% above) to 40% under (behind the hands): **Clubhead on the swing plane** | 10–30% above (*slightly above*; a little above is forgivable) or 40–70% under (*well under*) | more than 30% above (≈15 cm): **clubhead above the swing plane** (over the top); more than 70% under: **too far under** (stuck, too flat) |
| **Vs your takeaway** (shallowing) | that distance minus the same one at your takeaway: + = the club comes down flatter than it went back | 0% or more flatter: **Flatter than going back** | up to 20% steeper | more than 20% steeper than going back: the over-the-top loop |
| **Spine bend kept** | spine bend on the downswing frame vs address, from tracking; its lines are drawn only when it's off | up to 5° more upright or 5° more bent | 5–10° (*slightly standing up* / *slightly bending over*) | more than 10° more upright: **standing up** coming down (where early extension starts); more than 10° more bent: **bending over** |

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
under **Impact frame** on the results page if it's off); no extra marks. Settings live
in `[analyzers.impact]`. No reference photo: defined from the two classic
down-the-line impact checks.

| Measurement | How | 🟢 Green | 🟡 Yellow | 🔴 Red |
|---|---|---|---|---|
| **Hips vs address** (the tush line) | the rear edge of your body outline at hip height (from segmentation), at impact vs address, as % of torso length | moved back, or up to 10% (≈5 cm) toward the ball: **Hips stay back** | 10–15% toward the ball | more than 15% (≈7.5 cm, about 3 in): **Hips toward the ball** (early extension) |
| **Spine bend kept** | forward bend of the hip-center → shoulder-center line at impact vs address | up to 10° more upright or 6° more bent: **Posture kept** | 10–15° more upright (*slightly standing up*) or 6–12° more bent (*slightly dipping*) | more than that: **Standing up** / **Dipping** |

Good players lose a few degrees of bend as the hips open (McIlroy about 7°)
and often move the hips a few cm toward the ball, so the bands leave room for
that. Readings: McIlroy 8% toward the ball and 7° more upright; Tiger 4–15%
*back* and 2–3° more bent (all green); an amateur swing 18% (≈9 cm) toward the
ball: early extension, red. The key frame shows the address tush line (white),
where the rear of the hips is at impact, and the spine now (colored) vs at
address (dashed).

**8. Follow-through (implemented).** On the **Follow-through** marking step,
move the slider to where your **trail arm is parallel to the ground after impact** (hands
about shoulder height: the mirror of halfway back) and click the **clubhead**
and your **hands**. From behind, the hands are often hidden behind your body
here: click the lowest point of the shaft you can see instead (any two points
on the shaft define its line), and if the arms are hidden, pick the frame
where the shaft looks about as steep as at halfway back. Settings live in
`[analyzers.follow_through]`.

| Measurement | How | 🟢 Green | 🟡 Yellow | 🔴 Red |
|---|---|---|---|---|
| **Shaft points at** | the shaft line carried down to the ball's level, as at halfway back | 25% past the ball to 75% inside: **Exits on the swing plane** | to 50% past (*slightly flat*) or 75–110% inside (*slightly steep*) | beyond: **Exits flat** / **Exits steep** |
| **Vs halfway back** | this landing vs the halfway-back landing, as % of torso length | within ±60%: **Same line as going back** | 60–100% apart (*slightly steeper / flatter than going back*) | more than 100% apart |

The bands are loose on purpose: the ball is gone by the follow-through, so it
mostly reflects what came before. Only a clearly different exit turns red, and
these rows rank lowest when picking **Work on first** (a red follow-through is
only the focus when nothing else is red).

Set from the same reference golfer (follow-through on the ball, halfway back
16–26% inside: about 20% apart, green). McIlroy exits 48% inside, 18% steeper
than his halfway back (green); Jolo exits 51% steeper (green); an amateur swing exits on the ball but its
halfway back was laid off 117% past the ball, so the exit is 117% steeper than
the way back (red). Same-line needs halfway back marked; otherwise only the
shaft row. The key frame shows the shaft line carried to the ball's level and
where the halfway-back line landed (grey), joined by a tick.

**Notes:**
- Each club-based checkpoint (3, 4, 5, 6, 8) has a required marking step where
  you pick the frame and click the clubhead (and hands, where the check needs
  them), stored in `marks.json` under `checkpoints`, because the pose model only
  tracks the body. Address is the frame you mark the ball and club on; impact
  is found automatically (adjustable on the results page). Swings marked before
  every step was required still open; their unmarked checkpoints show as not
  measured.
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

### Hosting online (planned)

SwingCheck runs on your own computer today. The plan is to host it on one cheap
server so anyone can use it for free, with Ko-fi and InstaPay tips covering the cost.

**What the app needs from a server.** CPU for a minute or two per swing (ffmpeg
conversion, MediaPipe pose on every frame, the annotated video), about 1–2 GB of
RAM while a swing is processed, and disk for the swings (tens of MB each). It's
one process with jobs in memory and swings as folders, so a single always-on
server fits.

**Where.** Prices are rough; check before buying.

| Option | Cost | Fit |
|---|---|---|
| **Hetzner Cloud, 2 vCPU / 4 GB** | ~€4–6/month (EU), more in Singapore | **Suggested.** Enough RAM for MediaPipe, real disk; the Singapore region is close to Philippine users |
| DigitalOcean / Vultr / Linode, 2 GB | ~$12/month | Easy, but more money for less; the $4–6 1 GB plans are too small |
| Oracle Cloud free tier (ARM) | free | MediaPipe on ARM can be a hassle, and free accounts get reclaimed |
| Render / Railway / Fly free tiers | free–cheap | Poor fit: they sleep, have little RAM, and the disk can be wiped |

Plus a domain (~$10/year) with Cloudflare's free plan in front for HTTPS,
caching and basic abuse protection.

**Before going public:**

1. ✅ **Privacy between users.** Done: an owner key in a cookie, with no sign-in
   and no database (see "Hosted mode" below).
2. ✅ **Limits.** Done: each visitor keeps at most **4 swings** (delete one to add
   another), uploads up to 95 MB (Cloudflare's free plan refuses uploads over
   100 MB) and 20 seconds, one job at a time, and "busy, try again" past 10
   waiting jobs.
3. ✅ **Automatic cleanup.** Done: swings are deleted **3 days** after upload. The
   original upload is kept until then, so Trim still works; with 4 swings for 3
   days the disk per visitor stays small.
4. ✅ **Wording and legal.** Done: Terms of use (`#/terms`) and a Privacy notice
   (`#/privacy`) in the app, linked from every page's footer, which also says
   results are estimates, not coaching or medical advice; the PDF says it too.
   Hosted uploads need an "I agree" tick, checked by the server and saved in
   `swing.json` with the terms version (`TERMS_VERSION` in `static/legal.js`;
   bump it when the wording changes). The McIlroy example frames stay, with a
   not-affiliated note in the terms. Not reviewed by a lawyer.
5. ✅ **Restarts.** Done: a job lost to a restart says so. Analysis just needs
   Analyze again; a lost conversion shows "Convert again".

**Hosted mode (built).** `swingcheck --hosted` turns it on; run without it, the
app stays single-user exactly as before. The code is in `swingcheck/app/hosted.py`
and the limits in `[hosted]` in `config/default.toml`.

- **Owner key.** On the first visit the server gives the browser a random key in
  a cookie (HttpOnly, SameSite=Lax, Secure over HTTPS). Each new swing records a
  hash of it in its own `swing.json`, so the swings folder stays the only
  storage: no database. Every swing route (list, detail, frames, files, PDF,
  marking, analysis, jobs, delete) checks the owner and answers "not found" for
  anyone else's swing. Swing IDs are random (128 bits), with the name kept for
  display.
- **Private link.** Your swings shows "Copy private link"
  (`/#/claim/<key>`). Opening it on another device shows the same swings there.
  The key sits after the `#`, so it never reaches the server's or Caddy's logs,
  and the app removes it from the address bar once used. Losing both the cookie
  and the link loses the swings, which is fine since they expire anyway.
- **Limits.** Too big, too many swings, too many uploads from one IP address in a
  day (`max_uploads_per_ip_per_day`, so clearing cookies doesn't mean unlimited
  uploads) or too busy is refused before the upload is received. A clip over the length limit is deleted right after upload. The
  upload page shows the limits, and says so when you already have 4 swings.
- **Expiry.** A background sweep deletes swings 3 days after upload, at startup
  and every 30 minutes. Each card and swing page says when ("Deleted Oct 8").
- **Search engines.** Every response is marked `noindex`.
- Sign-in with accounts is not planned (it would need a database to maintain).

**Running it.** Docker, run as a service, Caddy in front for automatic HTTPS.
Start it with `swingcheck --hosted --runs-dir <folder>`: it listens on
127.0.0.1:8765 for Caddy, which forwards to it. In Caddy, also set a request body
limit a little over `max_upload_mb`, and with Cloudflare in front, set
`trusted_proxies` to Cloudflare's IP ranges so the per-IP upload limit sees
visitors' addresses rather than Cloudflare's.
Back up the swings folder, or treat swings as disposable. Time one swing on a PC
first to know how many swings a 2-CPU server handles per hour.

**Current server: https://swingcheck.org.** Hetzner CX23 (2 vCPU, 4 GB,
Nuremberg), Ubuntu 24.04, domain at Cloudflare (proxied, SSL mode Full (strict)).
2 GB swap, ffmpeg, Python 3.11 via uv, the app in `/opt/swingcheck/app` (cloned
with a read-only GitHub deploy key) as the `swingcheck` user, run by the systemd
service in [deploy/swingcheck.service](deploy/swingcheck.service). Caddy
([deploy/Caddyfile](deploy/Caddyfile)) gets Let's Encrypt certificates, trusts
`CF-Connecting-IP` only from Cloudflare's ranges and hands the app the visitor's
address (checked: the app sees the visitor, not Cloudflare). ufw allows SSH from
anywhere and 80/443 only from Cloudflare's ranges, so the server can't be reached
around Cloudflare. If Cloudflare's ranges change (cloudflare.com/ips), update both
the Caddyfile and the ufw rules. Checked through Cloudflare: a 94 MB upload goes
through (23 s from a Manila home line), 96 MB is refused at once.
A bare server also needs `libegl1 libgles2 libgl1`: MediaPipe's pose model fails
to load without them (the tests pass anyway, since they don't run the model).
Full analysis takes about 1.3–1.4× a Ryzen 7 5800H laptop: 73 s for McIlroy
(657 frames), 98 s for a 240 fps clip (774 frames). Releases go out with
`deploy/deploy.sh` (see Development: Releasing).

**Scaling notes.** One app process only: jobs live in memory, so never run
several workers. Jobs run one at a time (pose uses the whole CPU), so grow with a
bigger server, not more processes. Frame images use one lock per open video, so
visitors moving through frames of different swings don't wait for each other, and finished jobs
are forgotten after 6 hours.

**Frame speed on the marking screen.** Each frame is a round trip (about 300 ms
from Manila to Germany through Cloudflare) plus a seek on the server. Converted
videos get a keyframe every 15 frames (`[ingest] keyframe_interval`): x264's
default of 250 left 1–3 keyframes per clip, and a jump or a step back cost
250–450 ms of decoding on the 2-CPU server. The browser asks for one frame at a
time, newest wins (dragging the slider never queues up frames already passed),
keeps frames it has loaded (frame URLs carry the conversion's token, `?c=`, and
are cached `private` so Cloudflare never stores them), and once a frame settles
it loads the full-resolution copy and the neighbours (±1, ±2, ±3, ±10), so the
‹ › buttons and arrow keys show the next frame without a round trip.

Not done yet: listing a visitor's swings reads every
swing folder on the server to find theirs; once there are many visitors, keep
each owner's swings in their own subfolder.

**Later, cheapest long term.** MediaPipe also runs in the browser. Moving pose
detection onto the user's device would leave the server serving static pages
only (free on Cloudflare Pages or GitHub Pages): no uploads, no storage, no
privacy worries. A big rewrite, so only if usage grows.

### Left-handed golfers (done)

Each swing has its own handedness, chosen on the upload page (remembered in the
browser) and switchable on the marking screen. Every check, drawing and the camera
check follow it; the McIlroy example is mirrored for a left-handed swing.

MediaPipe tracks a mirrored (left-handed) golfer far less surely: on a mirrored
copy of Tiger's clip the near knee scored 0.41 visibility against 0.99, so it went
unmeasured. So a left-handed swing is tracked on mirrored frames, and the points
are flipped back with left and right swapped (`MIRROR_INDEX` in
`swingcheck/pose.py`); the golfer always sees their own, unmirrored video.

Validated on mirrored copies of McIlroy, Tiger, Jolo and the amateur swing
(video and marks flipped, set to left-handed): every checkpoint matches the
original within about 2° or 2 cm, with the same "Work on first". The only status
differences are rows sitting on a band edge (e.g. spine 26° vs 27° at the red
line), from re-encoding the flipped video.

### Other ideas, not planned yet

Backswing sway, vertical head movement, early extension, automatic club
detection, and trends across sessions.

---

## Setup (Windows)

1. **Python 3.11** ([python.org](https://www.python.org/downloads/)). Check with `py --version`. Use 3.11
   for the virtual environment: the app needs at least 3.11, and its MediaPipe and numpy versions are set up on it.
2. **ffmpeg**:

   ```bash
   winget install Gyan.FFmpeg
   ```

   Open a **new** terminal afterwards so `ffmpeg` is on your PATH.
3. **Install SwingCheck** from the project folder:

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
  left-hander, the left. Choose your handedness when uploading. If your setup
  is unusual, set `target_direction_fo` explicitly.
- Distance: full body plus the club at the top in frame (often 3 to 4 m).

---

## Using the app

1. **New swing.** Choose a down-the-line video (or drop it on the page). It
   uploads and converts with a progress bar; the conversion straightens rotated
   phone video and keeps the slo-mo frame rate. It then takes a quick look
   through the clip (about 5–20 s) to find your swing, so each marking step can
   open on a **suggested frame**, and checks the camera at address. (Face-on is
   shown but disabled until a future release.) Choose **Right-handed** or
   **Left-handed** under *Golfer*; the choice is remembered for next time, and a
   swing's handedness can be switched later on the marking screen (*Golfer*):
   the marks stay, and it's analyzed again.

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
   the line under it lists what's still to mark. The dark bar above the frame
   says what to click next in large type, with exactly where under it (for
   example *Click the ball*, *Center of the ball*); it flashes when it changes.
   Each step opens on its suggested frame (the caption says *Suggested frame*); check it and move the slider to
   the exact frame if needed with the slider, the ‹ › buttons or the arrow keys
   (Shift = 10 frames). **Back to the suggested frame** returns to it.

   **Address.** Move the slider to your set-up position, then click:
   - the **ball**
   - the **club neck**, where the shaft goes into the clubhead (the hosel), not
     the clubface: the shaft line through it is your swing plane
   - your **hands**, the middle of your grip, between your two hands

   A magnifier follows the cursor; on a phone, touch and hold, slide to aim with
   the magnifier above your finger, and let go to place the point. **Undo**
   (above the frame) removes the last point, and **Clear step** removes all of
   this step's points. **The frame you mark on is your address frame**:
   the address checks are measured on it, so pick a frame where you're fully set
   up and still. If a swing was saved with the wrong camera view or
   handedness, switch it under **Camera view** or **Golfer** below the marking
   panel.

   **Takeaway.** Switch to the **Takeaway** step, move the slider to where the
   shaft is parallel to the target line (from behind it points at the camera),
   and click the **clubhead**. That frame becomes the takeaway checkpoint.

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

   **Example to follow.** Below the points to click (so they and **Save and
   analyze** stay in view), Rory McIlroy is shown in the same position with that
   step's marks, so you can see what to look for
   and where to click. The frames ship with the app
   (`swingcheck/app/static/reference/`); rebuild them from any fully marked
   swing with `python -m swingcheck.app.make_reference runs/<swing-folder> "Name"`.

   **Mark checks.** Marks that look wrong get a yellow note under the points and
   a **!** on the step: hands below the club neck at address, the club neck far
   from the ball, the clubhead below your hands at halfway back or the
   follow-through, a step whose frame comes before the previous one, or a
   clubhead much too far from your hands. They never block saving; **Save and
   analyze** asks once whether to go ahead.

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

### Where your swings are stored

Each swing is a folder in `runs/` in the project. It holds the original upload,
the converted video, your marks, the analysis, `annotated.mp4`, the key frame
images and `report.txt`. Back up or delete that folder like any other files.

---

## Reading the results

The results page opens with a **swing summary**: one numbered dot per
checkpoint (green, yellow, red; dashed = not measured yet), how many are good /
to watch / to fix, and **Work on first**: the one fault to work on, with its
fix and the measurement behind it ("Biggest issue"). Tap a dot to jump to that
checkpoint.

**Reading the drawings.** Every key frame and the annotated video use one
drawing language (also under **How to read the drawings** beside each key frame
in the app; the marking screen uses the same shapes, as outlines with a center
dot so you can see exactly what you clicked):

| Look | Means |
|---|---|
| Green / yellow / red | something measured, colored by its result (its line, tick, mark and label) |
| White, usually dashed | a target or an address reference: where it should be, or where it was at address |
| Magenta line, grey lines either side | the swing plane (checkpoint 2) and its on-plane zone |
| Cyan | an earlier checkpoint's position, e.g. the clubhead at the takeaway |
| Solid circle | the clubhead |
| Solid square | the hands |
| Hollow ring | the ball, a heel, or where a shaft line lands |

How **Work on first** is picked (`swingcheck/priority.py`): every yellow or red
measurement gets a score = how deep into its band it is × how much that kind of
fault matters.

- **Depth:** 0–1 across the yellow band; past the red limit, 1 plus how many
  more yellow-band widths it goes. So "barely red" scores about 1, and a fault
  twice as far past red as the yellow band is wide scores 3.
- **Importance tiers** (weights 1.5 / 1.0 / 0.6):
  1. faults that cost shots directly: the club over the top or stuck coming down,
     and coming down steeper than it went back (6), early extension and standing
     up / dipping at impact (7);
  2. positions (the default): setup, and the club at each checkpoint;
  3. contributors: posture and trail knee kept through the backswing and
     downswing (3–6).
- A red always beats a yellow; among the same color the higher score wins, and
  swing order breaks ties. With nothing red it says **Worth a look** instead.

So a tier-1 fault just past red (1.5) beats a tier-2 one a little further in,
but a position that's far into red (say the shaft pointing well past the ball)
still comes first. Swings analyzed before this change use the old rule (first
red in swing order) until re-analyzed.

Below it, the checkpoints go one at a time (‹ › or the arrow keys), opening
on the one to work on first: the checkpoint's key frame next to its card, which
gives the result, what it means, **How to fix** when it's yellow or red, and
each measurement with its limits (the biggest issue is highlighted). The
annotated video and the impact frame setting sit beside it on a wide
screen and below it on a phone. **Re-analyze** is the main button; **Download
summary** saves a PDF to share outside the app (scorecard, the one thing to work
on first, then each checkpoint's key frame, readings with their limits, and how
to fix), built from the last analysis; **Edit marks**, the text report and
**Delete** are in the ⋯ menu. In the annotated video, the
header names only the checkpoint whose lines are on screen.

On the swing list, each analyzed swing shows the same 8 dots under its
thumbnail; swings still to mark or analyze say what's next.

Every measurement is 🟢 **Good**, 🟡 **Watch** (just outside good, worth a
look) or 🔴 **Fix**. Under each value the card lists its **Good** range (green)
and its **Fix** range (red); anything in between is Watch. Angles are in whole
degrees. Distances are rough whole **centimetres**, worked out from a **percent
of your torso length** (hip center to shoulder center, at address), so they
don't depend on the camera distance. The cm come from `[golfer] torso_cm` in
the config (50 cm unless you set yours).

**Address posture.** Measured on the frame you marked, using the body points on
the camera side (your trail side). Default ranges are in the [Roadmap](#roadmap).

- **Arms:** the shoulder-to-wrist line should hang straight down. Shown in
  degrees from vertical, *out* (hands reaching toward the ball) or *in* (tucked
  in toward the body).
- **Spine bend:** forward bend of the hip-to-shoulder line from vertical.
- **Knee bend:** 0° = straight leg.
- **Upper back:** how far the outline of your back curves out beyond a straight
  line between hip and shoulder level, in cm, measured from the body silhouette.
  A rounded upper back (hump) reads higher.

The address key frame draws each line with its value in its color (green,
yellow or red), plus dashed white aim lines for anything not green.

**Swing plane.** The magenta line on the address key frame runs along your shaft,
from the clubhead up through your hands to where it meets your body; the white
band on the torso is the belt-buckle zone it should hit. **Shaft points at**
says whether it points at your belt buckle, above or below your belt, and what
that means; the value is how far above your hips it crosses, in cm. The shaft
angle has a broad range, since it changes with the club and camera height.

Face-on checks are described in the [Roadmap](#roadmap) (future release).

---

## Tuning

All thresholds are in [`config/default.toml`](config/default.toml), each with a
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

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `ffmpeg not found on PATH` (conversion fails) | Install it (Setup step 2), open a new terminal, and start the app again. |
| Warning that the clip is 30 or 60 fps when you filmed slo-mo | The file was re-exported on the way off the phone. Use the original (see Filming). |
| Phone can't open the app | Start with `swingcheck --phone`, check the phone is on the same Wi-Fi, and allow Python through the Windows firewall on private networks. |
| "Can't reach the SwingCheck app" or "The app was restarted while this was running" | The app stopped (its terminal was closed or it was restarted) during a conversion or analysis. Analysis runs inside the app, so closing it stops the job. Start `swingcheck` again and press **Try again**. |
| Address checks measured on the wrong frame | **Edit marks**, move the slider to your set-up position, and save again. |
| Upper back reads rounded but isn't | Loose clothing changes the outline; check the line drawn on the address key frame. |
| Wrong impact frame | **Adjust impact** under Impact frame on the results page. |
| A check says "Not measured" | A body point wasn't tracked at that moment: usually lighting, part of the body out of frame, or baggy clothing. |
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
✅ in the [Roadmap](#roadmap), and update the expected list in
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

---

## Development

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

It waits until no analysis is running (a restart loses running jobs; it asks
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
    make_reference.py builds the McIlroy example frames in static/reference/
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
