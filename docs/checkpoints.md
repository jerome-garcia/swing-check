# Checkpoints and ranges

What each down-the-line checkpoint measures, its green, yellow, and red ranges, and the reference swings they were set on. All settings are in [`config/default.toml`](../config/default.toml).

**What "plane" means here.** The **swing plane line** is the one from
checkpoint 2: your shaft at address (clubhead through grip), extended so it
points at your belt buckle. It's drawn in magenta and is the only line called
"swing plane". Takeaway (3) and downswing (6) check that the **clubhead** stays
on or near it. Halfway back (4) and follow-through (8) check where the shaft
itself points at the ball's level. The top (5) checks the lead arm against the
spine.

The swing plane line is drawn across the whole frame, with a grey boundary
line either side marking the on-plane corridor (the takeaway's green band: 20% of
torso length, about 10 cm, toward you, `line_tolerance`, and 40%, about 20 cm,
toward the ball, `line_tolerance_outside`), on every checkpoint's key
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
| Arms hang straight down | shoulder → wrist line, degrees from vertical (+ reaching out, − tucked in) | within ±10° (driver ±20°) | 10–15° (driver 20–25°) | past 15° (driver 25°) |
| Spine tilt | forward bend of the hip-center → shoulder-center line from vertical | 30–45° (driver 25–40°) | 25–30° or 45–50° (driver 20–25° or 40–45°) | below 25° or above 50° (driver 20° / 45°) |
| Knee bend | knee flex = 180° − the hip-knee-ankle angle (0° = straight leg) | 15–35° | 10–15° or 35–40° | below 10° or above 40° |
| Upper back (rounding) | how far the outline of your back bulges beyond a straight line from hip to shoulder level, from the body silhouette (MediaPipe segmentation), as % of torso length | up to 6% (≈3 cm) | 6–9% | past 9% (≈4.5 cm) |

**Driver or wood.** With a driver you stand taller, the hands sit further out, and
the shaft is flatter, so a swing marked *Driver or wood* uses the driver ranges in
brackets above (`[clubs.driver]` in `config/default.toml`, set by hand for now:
there's no pro driver clip to tune them on yet). Everything else is the same.

When something is out of range, the card says how far and which way to move,
rounded up so following it lands you in green (e.g. *Spine bend 29°: Bend 2°
more*, with *Good 30–45°* and *Fix under 25° or over 50°* below it; a row that's
never red, like the shaft angle or the trail knee, says *Fix none (a watch item
only)*), and the
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
| **Shaft angle** | angle of the line above horizontal | 45–65° (driver 35–55°) | outside green: *slightly* flat or steep, or *too* flat or steep past 40° / 70° (driver 30° / 60°) | never: it depends on the club and camera height as much as the setup, so it's a watch item at most (with a tip to check them) |

**The swing plane line** that checkpoints 3–8 are judged against starts at the
address clubhead and points at the belt buckle. When your shaft already points
there (green), it is your shaft line. When it doesn't, the plane runs to the
nearest edge of the belt-buckle zone instead (0% or 45% up the torso), and your
shaft is drawn dashed to where it points. So a too-upright setup (hands high,
standing close) doesn't give you a too-upright plane to swing along, and a
too-flat one doesn't give you a too-flat plane. Swings that point at the belt
buckle, including McIlroy's and Tiger's, are unchanged.

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
| **Clubhead vs swing plane** | distance of the clubhead from the swing plane line (checkpoint 2's line, toward the belt buckle), square to it, as % of torso length | up to 20% (≈10 cm) toward you or 40% (≈20 cm) toward the ball (good players often go back a little outside; Tiger ≈18 cm): **Clubhead on the swing plane** | 20–50% toward you or 40–50% toward the ball: *clubhead slightly toward you / toward the ball* | past 50% (≈25 cm): *clubhead too far toward you* (pulled inside or rolled open) or *too far toward the ball* (picked up outside) |
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
clubhead staying on the swing plane line is the cleaner on-plane test.

Good players vary here, which is why the yellow band is wide: McIlroy reads 4%
outside (on plane); Tiger 38% inside on one clip and 21% outside on another;
Morikawa by eye goes back with the clubhead outside his hands; an amateur swing
taken away low and inside reads 50%, right at the red line. Camera aim also
matters: the clubhead is about a metre closer to the camera than at address,
so a camera pointed 5° off the target line moves it sideways by about 18% of
torso length. The thresholds (`line_tolerance`, `flag_distance`) are a first
guess from these few swings; tune them as more clips come in.

The key frame shows the swing plane line (magenta) with the on-plane band
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
| **Hands vs back heel** | how far the hands sit across the picture from straight above the back (trail) heel (tracked, median of a few frames around the top), as % of torso length; drawn as a dashed plumb line up from the heel | within ±15% (about 7 cm): **Hands over your back heel** | 15–30% (*hands slightly toward the ball* / *slightly behind your back heel*); past 30% the wording says **too far toward the ball** or **behind your back heel** (deep, flat), still yellow | never: it varies with the club (a driver is flatter) and the camera angle, and rarely costs a shot by itself |
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
unreliable, but the clubhead's position against the swing plane line is
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
| **Shaft points at** | the shaft line carried down to the ball's level, as at halfway back | 70% past the ball (≈35 cm; pros often exit a little flat, Tiger ≈28 cm) to 40% inside (≈20 cm toward your feet, as at halfway back): **Exits on the swing plane** | to 100% past (*slightly flat*) or 40–110% inside (*slightly steep*); beyond: **Exits flat** / **Exits steep**, still yellow | never |
| **Vs halfway back** | this landing vs the halfway-back landing, as % of torso length | up to 60% steeper or 90% flatter (≈30 / 45 cm; pros lean flatter, Tiger ≈34 cm): **Same line as going back** | 60–100% steeper or 90–130% flatter (*slightly steeper / flatter than going back*); beyond: *steeper / flatter than going back*, still yellow | never |

The bands are loose on purpose: the ball is gone by the follow-through, so it
mostly reflects what came before, good players exit in different ways, and a
late frame or a driver makes the exit look flatter. So the follow-through is
**Watch at most, never Fix**, and its rows rank lowest when picking **Work on
first**.

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

## Reading the results

The results page opens with a **swing summary**: one numbered dot per
checkpoint (green, yellow, red; dashed = not measured yet), how many are good /
to watch / to fix, and **Work on first**: the one fault to work on, with its
fix and the measurement behind it ("Biggest issue"). With nothing red, it's
**Worth a look** instead, and when every checkpoint was measured a green **Good
swing** note comes first ("Nothing to fix right now"); all green and all measured
is **Tour-level swing**. Tap a dot to jump to that
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
gives the result, what it means, **What to try** when it's yellow (**How to fix** when red), and
each measurement with its limits (the biggest issue is highlighted). The
annotated video and the impact frame setting sit beside it on a wide
screen and below it on a phone. The buttons are **Download PDF** and **Share
PDF** (the main one): the PDF has the scorecard, the one thing to work on first,
then each checkpoint's key frame, readings with their limits, and how to fix,
built from the last analysis. **Edit marks**, **Re-analyze**, the text report,
**Stop sharing** (once shared), and **Delete** are in the ⋯ menu. The pencil after the swing's
name turns it into a text box to rename it (up to 60 characters); a swing starts with its video's file name, and the
name also goes on its PDF, so a shared PDF is made again with the new one. In the annotated video, the
header names only the checkpoint whose lines are on screen.

**Share PDF** makes a link anyone can open (`/s/<code>`, opens the share
sheet on a phone, copies the link on a computer) that goes straight to the summary
PDF. Messenger and similar apps show a preview card for it (the address, top, and
impact frames and the checkpoint counts), read from a tiny page that sends a
browser on to the PDF at once. It's a snapshot saved inside
the swing's folder (`swingcheck/app/share.py`): never the video or its file name,
and the code is random and separate from your key. It follows the latest
results: each re-analysis updates what the link shows, at the same link.
A short note under the header says it's shared, with **Copy link** and **Open link** (the shared PDF in a new tab, as others see it). **Stop
sharing** (⋯ menu) ends it at once, and it ends anyway when the swing is deleted.

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
the camera side (your trail side). Default ranges are under checkpoint 1 above.

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


## Left-handed golfers

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

## Face-on (future release)

Built and unit-tested on made-up data, but not yet validated on real clips, so
it's switched off in the app (`FACE_ON_ENABLED` in `swingcheck/app/server.py`).
Swings already saved as face-on can still be opened, and switched to
down-the-line from the marking screen.

| Check | What it tells you |
|---|---|
| **Hands at impact** | Hands ahead of, level with, or behind the ball (scoop / shaft lean) |
| **Weight shift** | How far the hips moved toward the target by impact (low point / fat shots) |
| **Head drift** | Whether the head moved away from the target by impact |
