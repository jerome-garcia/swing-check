# Hosting and operations

How swingcheck.org runs: the server, hosted mode, the admin page, and how it
can grow. For releasing, see [development.md](development.md#releasing).

## The server

| | |
|---|---|
| **Site** | https://swingcheck.org |
| **Machine** | Hetzner CX23: 2 vCPU, 4 GB RAM, 2 GB swap, Nuremberg |
| **System** | Ubuntu 24.04, Python 3.11 (via uv), ffmpeg |
| **App** | `/opt/swingcheck/app`, run as the `swingcheck` user by systemd ([deploy/swingcheck.service](../deploy/swingcheck.service)) |
| **Web server** | Caddy ([deploy/Caddyfile](../deploy/Caddyfile)), Let's Encrypt certificates |
| **In front** | Cloudflare (proxied, SSL mode Full (strict)), which also holds the domain |

How a request gets in: **Cloudflare → Caddy → the app** on `127.0.0.1:8765`.

- **Firewall (ufw):** SSH from anywhere; ports 80 and 443 only from Cloudflare's
  IP ranges, so the server can't be reached around Cloudflare.
- **Visitor addresses:** Caddy trusts `CF-Connecting-IP` only from Cloudflare's
  ranges and passes the visitor's address to the app (for the per-IP upload
  limit). If Cloudflare's ranges change (cloudflare.com/ips), update both the
  Caddyfile and the ufw rules.
- **Code:** cloned with a read-only GitHub deploy key. The server only ever runs
  a release tag; never edit code there.
- **System packages:** a bare server also needs `libegl1 libgles2 libgl1`, or
  MediaPipe's pose model fails to load (the tests pass anyway, since they don't
  run the model). New packages are the one thing installed by hand; list them here.

**Speed.** A full analysis takes about 1.3–1.4× as long as on a Ryzen 7 5800H
laptop: 73 s for McIlroy (657 frames), 98 s for a 240 fps clip (774 frames).
Through Cloudflare, a 94 MB upload takes about 23 s from a Manila home line.

## Hosted mode

`swingcheck --hosted` turns it on; without it, the app is single-user. The code
is in `swingcheck/app/hosted.py` and the limits in `[hosted]` in
`config/default.toml`.

- **Owner key, no accounts.** On the first visit the browser gets a random key
  in a cookie (HttpOnly, SameSite=Lax, Secure). Each swing stores a hash of it in
  its `swing.json`, so there's no database. Every swing route checks the owner
  and answers "not found" for anyone else's swing. Swing IDs are random (128 bits).
- **Private link.** "Copy private link" (`/#/claim/<key>`) opens the same swings
  on another device. The key sits after the `#`, so it never reaches the
  server's or Caddy's logs, and the app removes it from the address bar.
- **Limits.**

  | Limit | Value |
  |---|---|
  | Swings per visitor | 4 (delete one to add another) |
  | Upload size | 95 MB (Cloudflare's free plan refuses over 100 MB) |
  | Clip length | 20 seconds |
  | Uploads per IP address per day | `max_uploads_per_ip_per_day`, so clearing cookies isn't a way around the limit |
  | Waiting jobs | 10, then "busy, try again" |
  | Free disk | under 5 GB (`min_free_gb`), new uploads are paused with "SwingCheck is full right now"; they open again as expired swings are deleted, and the admin page shows it |

  Uploads over a limit are refused before they're received; a clip that's too
  long is deleted right after upload. Caddy's request body limit is set a little
  over `max_upload_mb`.
- **Expiry.** Swings are deleted 3 days after upload, by a sweep at startup and
  every 30 minutes. Each swing says when ("Deletes on Oct 8").
- **Terms.** Uploads need an "I agree" tick, checked by the server and saved
  with the terms version (`TERMS_VERSION` in `static/legal.js`; bump it when the
  wording changes). The Terms of use and Privacy notice are at `/terms` and
  `/privacy`. Not reviewed by a lawyer.
- **Restarts.** A job lost to a restart says so: analysis needs Analyze again, a
  conversion shows "Convert again". The release script waits for jobs to finish
  first.
- **Search engines.** Every response is marked `noindex`.

## Admin page

`/admin` shows counts and timings only, never anyone's swings, videos, names, IP
addresses, or keys:

- what's running, the queue, uploads in progress, disk, and version;
- uploads, conversions, and analyses per day for a week, with failures;
- typical (median) wait, analysis, and marking time;
- recent errors and the most common camera-check findings;
- feedback from the footer's Feedback page: the average rating, how many of each, and the latest
  messages (saved in `feedback.jsonl` next to the swings, with no IP address or key, and kept until
  deleted by hand);
- how many browsers uploaded each day, from a code that changes daily and is
  never saved, so days can't be linked.

The numbers come from `admin-events.jsonl` in the swings folder (event, time,
durations, and errors), kept 90 days; the Privacy notice says so.

**Access.** Cloudflare Access guards `/admin` with an email one-time code, and
the app also checks that email against `SWINGCHECK_ADMIN_EMAIL`, set in a
systemd drop-in on the server (not in the repo). Without it the page doesn't
exist. Locally it's open.

## Performance notes

**Marking screen frames.** Each frame is a round trip (about 300 ms from Manila
to Germany) plus a seek on the server. To keep it quick:

- converted videos have a keyframe every 15 frames (`[ingest] keyframe_interval`),
  so jumping around doesn't mean decoding hundreds of frames;
- the browser asks for one frame at a time, and the newest request wins;
- loaded frames are cached in the browser (`private`, so Cloudflare never stores
  them), and once a frame settles the neighbours (±1, ±2, ±3, ±10) load ahead,
  so ‹ › and the arrow keys feel instant;
- each open video has its own lock, so visitors on different swings don't wait
  for each other.

**Queue.** A waiting job shows its place in line and a rough wait ("1 swing
ahead of yours, about 2 min", from `TYPICAL_S` in `jobs.py`). Finished jobs are
forgotten after 6 hours.

## Scaling

**Today's limits.**

- **One app process only.** Jobs live in memory, so never run several workers.
- **One job at a time.** Pose tracking uses the whole CPU, so a bigger server
  helps; more processes don't. At about 1.5 minutes per swing, the current
  server handles roughly 40 swings an hour.
- **Disk.** Key frames are saved at most 1920 px on their longest side (`[output] key_frame_max_size`), about a quarter of a 4K PNG. Swings are tens of MB each and expire after 3 days, so disk grows
  with daily uploads, not total users. The admin page shows disk use.

**Next steps, as usage grows:**

1. **A bigger server.** Hetzner can resize in place: more vCPUs mean faster
   analyses and shorter waits. The cheapest first step.
2. **Per-owner folders.** Listing a visitor's swings reads every swing folder to
   find theirs. With many visitors, keep each owner's swings in their own
   subfolder.
3. **Closer to Asia.** Many visitors are in the Philippines; a server in
   Singapore would cut the marking screen's round trip.
4. **Separate workers.** Move jobs out of the app's memory into a queue, so
   several machines can analyze at once. A bigger change, only when one server
   can't keep up.
5. **Pose tracking in the browser.** MediaPipe also runs in the browser. Moving
   it onto the golfer's device would leave the server serving static pages only
   (free on Cloudflare Pages): no uploads, no storage, and no privacy worries. A
   big rewrite, only if usage grows a lot.

**Backups.** Swings expire in 3 days, so they can be treated as disposable. The
code is in GitHub, and the server's setup is in `deploy/`.
