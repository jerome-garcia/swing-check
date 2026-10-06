# Hosting and operations

How swingcheck.org is hosted, its limits, privacy model, admin page, and performance notes.

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
4. ✅ **Wording and legal.** Done: Terms of use (`/terms`) and a Privacy notice
   (`/privacy`) in the app, linked from every page's footer, which also says
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
  and the app removes it from the address bar once used. (Every other page has a
  clean address, such as `/new` or `/swing/<id>/mark`, routed in the browser; the
  server answers each with the app, and old `#/` links still open the right page.) Losing both the cookie
  and the link loses the swings, which is fine since they expire anyway.
- **Limits.** Too big, too many swings, too many uploads from one IP address in a
  day (`max_uploads_per_ip_per_day`, so clearing cookies doesn't mean unlimited
  uploads) or too busy is refused before the upload is received. A clip over the length limit is deleted right after upload. The
  upload page shows the limits, and says so when you already have 4 swings.
- **Expiry.** A background sweep deletes swings 3 days after upload, at startup
  and every 30 minutes. Each card and swing page says when ("Deletes on Oct 8").
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
service in [deploy/swingcheck.service](../deploy/swingcheck.service). Caddy
([deploy/Caddyfile](../deploy/Caddyfile)) gets Let's Encrypt certificates, trusts
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
`deploy/deploy.sh` (see [development.md](development.md)).

**Admin page (`/admin`).** Numbers only, never anyone's swings, in the brand's look (deep-green bar, tiles, an hour-of-day line chart): what's running, the
queue, uploads in progress, disk, version; uploads, conversions, and analyses per day
for a week (with failures); typical wait, analysis, and marking time (from a video being ready to its marks first saved); recent errors; the most common camera-check findings; and how many browsers
uploaded each day (a code from the browser's key and a secret that changes daily and
is never saved, so days can't be linked). Swings are deleted after 3 days,
so the counts come from `admin-events.jsonl` in the swings folder: event, time,
durations, and errors (swing folder blanked), no names, IPs, or keys, kept 90 days
(the Privacy page says so). Hosted, Cloudflare Access guards `/admin` with an email
one-time code, and the app also checks the email Access vouches for against
`SWINGCHECK_ADMIN_EMAIL` (set in a systemd drop-in on the server, not in the repo);
without it the page doesn't exist. Locally it's open.

**Scaling notes.** One app process only: jobs live in memory, so never run
several workers. Jobs run one at a time (pose uses the whole CPU), so grow with a
bigger server, not more processes. A queued job tells its page its place in line
and a rough wait ("1 swing ahead of yours, about 2 min", from `TYPICAL_S` in jobs.py). Frame images use one lock per open video, so
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
