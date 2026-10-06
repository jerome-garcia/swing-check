# Checkpoints and ranges

What each down-the-line checkpoint measures, its green, yellow, and red ranges,
and the reference swings they were set on. All settings are in
[`config/default.toml`](../config/default.toml).

## Basics

**Colors.** Every measurement is 🟢 green (Good), 🟡 yellow (Watch: just outside
good), or 🔴 red (Fix). A checkpoint takes the worst color of its measurements.

**Units.**
- Angles are in degrees.
- Distances are set as a **percent of torso length** (hip center to shoulder
  center at address), so they don't depend on camera distance.
- The app shows them as rough **cm**, from `[golfer] torso_cm` (50 by default,
  so 10% ≈ 5 cm).

**Wording.** Plain words first: *front* and *back* for lead and trail; *toward
you* and *toward the ball* for inside and outside. Each row shows its **Good**
and **Fix** range; anything between is **Watch**.

**The swing plane line.**
- Set at checkpoint 2: your shaft at address, extended to your belt buckle.
- Drawn in magenta, with grey lines either side marking the on-plane band
  (about 10 cm toward you, 20 cm toward the ball), on every key frame from 2 to
  8 and the whole annotated video.
- Takeaway (3) and downswing (6) check the **clubhead** against it.
- Halfway back (4) and follow-through (8) check where the **shaft** points at the
  ball's level.
- The top (5) checks the lead arm against the spine.

**Marking.** Checkpoints 3, 4, 5, 6, and 8 each have a marking step (frame plus
clubhead, and hands where needed), saved in `marks.json` under `checkpoints`,
since the pose model only tracks the body. Address is the frame you mark the
club on. Impact is found automatically.

## Overview

| # | Checkpoint | What it checks | Settings |
|---|---|---|---|
| 1 | **Address** | Arms hang straight, spine tilt, knee bend, back rounding | `[analyzers.address]` |
| 2 | **Swing plane** | The shaft at address points at the belt buckle | `[analyzers.swing_plane]` |
| 3 | **Takeaway** | Shaft parallel to the target line: the clubhead is on the swing plane | `[analyzers.takeaway]` |
| 4 | **Halfway back** | Lead arm parallel: the shaft points at or just inside the ball | `[analyzers.halfway_back]` |
| 5 | **Top** | The lead arm matches the shoulders, 90° to the spine | `[analyzers.top]` |
| 6 | **Downswing** | Shaft parallel coming down: on plane, flatter than the takeaway | `[analyzers.downswing]` |
| 7 | **Impact** | Hips stay back (no early extension), spine bend kept | `[analyzers.impact]` |
| 8 | **Follow-through** | Trail arm parallel: the club exits on the same line as halfway back | `[analyzers.follow_through]` |

## 1. Address

Measured on the frame you mark, using the body points on the camera side (your
trail side).

| Measurement | How | 🟢 Green | 🟡 Yellow | 🔴 Red |
|---|---|---|---|---|
| Arms hang straight down | shoulder → wrist line, degrees from vertical (+ reaching out, − tucked in) | within ±10° (driver ±20°) | 10–15° (driver 20–25°) | past 15° (driver 25°) |
| Spine tilt | forward bend of the hip-center → shoulder-center line from vertical | 30–45° (driver 25–40°) | 25–30° or 45–50° (driver 20–25° or 40–45°) | below 25° or above 50° (driver 20° / 45°) |
| Knee bend | knee flex = 180° − the hip-knee-ankle angle (0° = straight leg) | 15–35° | 10–15° or 35–40° | below 10° or above 40° |
| Upper back (rounding) | how far the outline of your back bulges beyond a straight line from hip to shoulder level, from the body silhouette, as % of torso length | up to 6% (≈3 cm) | 6–9% | past 9% (≈4.5 cm) |

- **Driver or wood:** uses the bracketed ranges (`[clubs.driver]`), set by hand
  for now.
- **Card:** says how far and which way to move, rounded so following it lands
  in green (e.g. *Spine bend 29°: Bend 2° more*).
- **Summary:** leads with the hips, since standing tall with straight knees and
  reaching arms usually comes from too little hip hinge.
- **Key frame:** a dashed white aim line for each yellow or red part: spine at
  37.5°, arm straight down, thigh at 25° of knee flex.

## 2. Swing plane

The line through the club neck (hosel) and grip you click at address.

| Measurement | How | 🟢 Green | 🟡 Yellow | 🔴 Red |
|---|---|---|---|---|
| **Shaft points at** (key check) | where the extended shaft line crosses your torso, as % of the way from hip center (0%) to shoulder center (100%) | 0–45%: **Points at your belt buckle** | −10–0%: *just below your belt*; 45–60%: *just above your belt* | below −10%: **Points below your belt** (too flat); above 60%: **Points above your belt** (too upright) |
| **Shaft angle** | angle of the line above horizontal | 45–65° (driver 35–55°) | outside green; *too* flat or steep past 40° / 70° (driver 30° / 60°) | never: a watch item (it depends on club and camera height) |

- **The plane used for checkpoints 3–8** starts at the address clubhead and points
  at the belt buckle. If your shaft is off, the plane runs to the nearest edge of
  the belt-buckle zone instead, and your shaft is drawn dashed. So a bad setup
  doesn't give you a bad plane to swing along.
- **Typical shaft angles:** driver 45–50°, mid-irons 50–55°, short irons and
  wedges 55–65°.
- **References:** Tiger 55° and McIlroy 58°, both pointing 25% up the torso.

## 3. Takeaway

Marking: the frame where the shaft is parallel to the target line (it points at
the camera); click the clubhead.

| Measurement | How | 🟢 Green | 🟡 Yellow | 🔴 Red |
|---|---|---|---|---|
| **Clubhead vs swing plane** | distance of the clubhead from the swing plane line, square to it, as % of torso length | up to 20% (≈10 cm) toward you or 40% (≈20 cm) toward the ball: **Clubhead on the swing plane** | 20–50% toward you or 40–50% toward the ball | past 50% (≈25 cm): *too far toward you* (pulled inside) or *too far toward the ball* (picked up outside) |
| **Spine bend kept** | spine bend vs address | up to 6° more upright or 5° more bent | 6–10° more upright or 5–10° more bent | more than 10°: **standing up** or **bending over** |
| **Back knee bend kept** | trail knee flex vs address | up to 5° straighter or 8° more bent | more than 5° straighter or 8° more bent | never: a watch item |

- **Why the wide band:** good players vary. McIlroy reads 4% outside, Tiger 38%
  inside on one clip and 21% outside on another (≈18 cm). An amateur swing taken
  away low and inside reads 50%, right at the red line.
- **Camera aim matters:** the clubhead is about 1 m closer to the camera here, so
  a camera 5° off the target line moves it about 18% of torso length.
- **Back knee is never red:** it rarely costs a shot by itself, and is hard to
  read once the hips turn.
- **References:** McIlroy loses 2° of spine bend and 3° of knee flex; Tiger 5.5°
  and gains 2°. All green.
- **Key frame:** the plane with its band, a tick from the clubhead to the line,
  and the hands for reference.

## 4. Halfway back

Marking: the frame where the lead arm is parallel to the ground; click the
clubhead (or the highest point of the shaft you can see) and the hands.

| Measurement | How | 🟢 Green | 🟡 Yellow | 🔴 Red |
|---|---|---|---|---|
| **Shaft points at** | the line from the clubhead through the hands, carried down to the ball's level, vs the ball, as % of torso length | 10% past the ball to 40% inside: **Points at the ball** | 40–70% inside (a little steep) or 10–25% past (a little flat) | past 70% inside: **Points at your feet** (too steep); more than 25% past: **Points well past the ball** (laid off) |
| **Spine bend kept** | spine bend vs address | up to 8° more upright or 5° more bent | 8–12° more upright or 5–10° more bent | more than 12° upright: **standing up**; more than 10° bent: **bending over** |
| **Back knee bend kept** | trail knee flex vs address | up to 6° straighter or 8° more bent | beyond that | never: a watch item |

- **References:** McIlroy 30% inside (green); an amateur swing 117% past the ball
  (laid off, red). Good players lose only a few degrees of posture here.
- **Dropped:** "the hands split the biceps". The trail elbow is half hidden from
  behind, so it couldn't be judged reliably.
- **Key frame:** the shaft line carried to the ball's level, and a tick to the ball.

## 5. Top

Marking: the frame where the club stops going back; click the clubhead and the
hands.

| Measurement | How | 🟢 Green | 🟡 Yellow | 🔴 Red |
|---|---|---|---|---|
| **Front arm vs spine** | angle between the lead arm (shoulder → hands) and the spine (hip center through the head); 90° = the arm matches the shoulders | 75–105° | 65–75° (*slightly above*) or 105–115° (*slightly below*) | under 65°: **above the shoulders** (upright); over 115°: **below the shoulders** (flat) |
| **Hands vs back heel** | hands across the picture from straight above the back heel, as % of torso length | within ±15% (≈7 cm) | beyond 15%, still yellow | never: varies with club and camera |
| **Spine bend kept** | spine bend vs address | up to 8° more upright or 5° more bent | 8–12° more upright or 5–10° more bent | more than 12° upright or 10° bent |

- **The spine runs through the head,** as golf instruction draws it. A line to
  the middle of the shoulders came out too upright once the shoulders turn.
- **References:** arm angle McIlroy 91°, Tiger 77° (green), an amateur 73°
  (yellow). Hands: McIlroy ≈2 cm, Tiger ≈6 cm toward the ball.
- **Dropped:** "hands in the plane zone".
- **Key frame:** the spine (white), the lead arm in its color, and a dashed line
  where the arm should be.

## 6. Downswing

Marking: the frame where the shaft is parallel to the ground coming down (hands
about hip height); click the clubhead.

| Measurement | How | 🟢 Green | 🟡 Yellow | 🔴 Red |
|---|---|---|---|---|
| **Clubhead vs swing plane** | clubhead distance from the line, square to it, as % of torso length | 10% above (≈5 cm) to 40% under: **on the swing plane** | 10–30% above or 40–70% under | more than 30% above: **over the top**; more than 70% under: **too far under** (stuck) |
| **Vs your takeaway** (shallowing) | that distance minus the takeaway's; + = flatter coming down | 0% or more flatter | up to 20% steeper | more than 20% steeper: the over-the-top loop |
| **Spine bend kept** | spine bend vs address | up to 5° either way | 5–10° | more than 10°: **standing up** or **bending over** |

- **Why compare with the takeaway:** the shaft points at the camera here, so its
  angle on screen is unreliable; the clubhead against the line isn't.
- **Shallowing needs the takeaway marked;** without it, only the plane check shows.
- **References:** McIlroy 13% under, 17% flatter than his takeaway (green); an
  amateur 28% steeper than going back (red).
- **Key frame:** a dashed line from the takeaway clubhead to this one.

## 7. Impact

Automatic, on the detected impact frame (adjustable on the results page). No
extra marks.

| Measurement | How | 🟢 Green | 🟡 Yellow | 🔴 Red |
|---|---|---|---|---|
| **Hips vs address** (the tush line) | the rear of your body outline at hip height, impact vs address, as % of torso length | moved back, or up to 10% (≈5 cm) toward the ball | 10–15% toward the ball | more than 15% (≈7.5 cm): **early extension** |
| **Spine bend kept** | spine bend vs address | up to 10° more upright or 6° more bent | 10–15° upright or 6–12° bent | more: **Standing up** / **Dipping** |

- **References:** McIlroy 8% toward the ball and 7° more upright; Tiger 4–15% back
  (green). An amateur 18% toward the ball (red).
- **Key frame:** the address tush line (white), the hips now, and the spine now
  vs at address (dashed).

## 8. Follow-through

Marking: the frame where the trail arm is parallel to the ground after impact;
click the clubhead and the hands (or the lowest point of the shaft you can see).

| Measurement | How | 🟢 Green | 🟡 Yellow | 🔴 Red |
|---|---|---|---|---|
| **Shaft points at** | the shaft line carried down to the ball's level | 70% past the ball (≈35 cm) to 40% inside (≈20 cm): **Exits on the swing plane** | to 100% past or 40–110% inside; beyond, still yellow | never |
| **Vs halfway back** | this landing vs the halfway-back landing | up to 60% steeper or 90% flatter (≈30 / 45 cm) | 60–100% steeper or 90–130% flatter; beyond, still yellow | never |

- **Watch at most, never Fix:** the ball is gone by now, good players exit in
  different ways, and a late frame or a driver looks flatter. It ranks lowest
  for Work on first.
- **References:** McIlroy 48% inside, 18% steeper than halfway back (green);
  Tiger ≈28 cm past, ≈34 cm flatter (green).
- **Key frame:** the shaft line at the ball's level and where the halfway-back
  line landed (grey).

## Work on first

Picked in `swingcheck/priority.py`. Each yellow or red measurement gets a
score: **depth × importance**.

- **Depth:** 0–1 across the yellow band; past red, 1 plus how many more
  yellow-band widths it goes.
- **Importance:**

  | Weight | Faults |
  |---|---|
  | 1.5 | Cost shots directly: over the top, stuck, steeper than going back (6); early extension, standing up or dipping at impact (7) |
  | 1.0 | Positions: setup, and the club at each checkpoint |
  | 0.6 | Contributors: posture and back knee kept (3–6) |

- **Red beats yellow.** Within a color, the higher score wins; swing order breaks
  ties. With nothing red, it says **Worth a look**.

## Results page

- **Summary:** one dot per checkpoint, counts of good, watch, and fix, and
  **Work on first**. **Good swing** when nothing is red; **Tour-level swing** when
  all eight are green.
- **Checkpoints:** one at a time, each with its key frame and a card (result,
  **What to try** or **How to fix**, and each row with its ranges).
- **PDF:** the scorecard, Work on first, then each checkpoint's key frame and
  readings.
- **Share link** (`/s/<code>`, `swingcheck/app/share.py`): a snapshot of the PDF,
  never the video or its file name. It updates on re-analysis and ends on
  **Stop sharing** or delete.

### Drawings

| Look | Means |
|---|---|
| Green / yellow / red | Something measured, colored by its result |
| White, usually dashed | A target, or where it was at address |
| Magenta line, grey lines either side | The swing plane and its on-plane band |
| Cyan | An earlier checkpoint's position, e.g. the takeaway clubhead |
| Solid circle | The clubhead |
| Solid square | The hands |
| Hollow ring | The ball, a heel, or where a shaft line lands |

## Left-handed golfers

- Each swing has its own handedness; every check, drawing, and the camera check
  follow it. The marking example is mirrored.
- MediaPipe tracks mirrored golfers less surely, so a left-handed swing is
  tracked on mirrored frames and the points flipped back (`MIRROR_INDEX` in
  `pose.py`). The golfer always sees their own video.
- **Validated** on mirrored copies of McIlroy, Tiger, Jolo, and an amateur
  swing: every checkpoint within about 2° or 2 cm of the original.

## Face-on (future release)

Built and unit-tested on made-up data, but not validated on real clips, so it's
off in the app (`FACE_ON_ENABLED` in `swingcheck/app/server.py`).

| Check | What it tells you |
|---|---|
| **Hands at impact** | Hands ahead of, level with, or behind the ball (scoop or shaft lean) |
| **Weight shift** | How far the hips moved toward the target by impact |
| **Head drift** | Whether the head moved away from the target by impact |
