# SwingCheck

**Free golf swing analysis from one phone video.** Try it at
**[swingcheck.org](https://swingcheck.org)**.

> **Alpha.** SwingCheck is in active development: features, results, and limits
> may change. Results are estimates from video, for practice only.

Film one swing from behind (down the line), mark a few points, and SwingCheck
grades eight checkpoints through your swing. You get an annotated video, key
frames, and the one thing to work on first, with a fix in plain words.

## Features

- **Eight checkpoints**, each graded green (Good), yellow (Watch), or red (Fix):

  | # | Checkpoint | What it checks |
  |---|---|---|
  | 1 | Address | Arms hang straight, spine and knee bend, upper back |
  | 2 | Swing plane | The shaft points at your belt buckle |
  | 3 | Takeaway | The clubhead stays on the swing plane |
  | 4 | Halfway back | The shaft points at the ball |
  | 5 | Top | The lead arm matches your shoulders, hands over the back heel |
  | 6 | Downswing | The club comes down on plane, flatter than it went back |
  | 7 | Impact | The hips stay back and the spine bend is kept |
  | 8 | Follow-through | The club exits on the same line as halfway back |

- **Work on first:** the one fault that matters most, with how to fix it.
- **Guided marking:** each step shows Rory McIlroy at the same moment (Tiger
  Woods for a driver) and the points to click.
- **Camera check:** says right away if the video is filmed from a usable angle.
- **Share your results** as a PDF link, with a preview card in chats.
- **Right- or left-handed**, and **iron or driver** ranges.
- **Private by design:** no sign-up; swings are deleted after 3 days.

Face-on analysis is planned for a future release.

## Filming your swing

- **Use a tripod.** The camera must not move during the clip.
- **Film from behind**, with the camera on the line through your hands, at hip
  height, aimed down the target line.
- **One swing per clip**, with your whole body, the ball, and the club at the
  top in frame.
- **Slo-mo if you have it** (120 or 240 fps). Upload the original from your
  camera roll: copies sent through chat apps are often re-saved at 30 fps.

The app also has a setup guide with pictures on the upload page.

## Privacy

On swingcheck.org, your swings are tied to a private key in your browser, not
an account. Nobody else can see them unless you share a PDF link. Videos are
deleted 3 days after upload. See the Terms of use and Privacy notice in the app.

## Run it on your own computer

Everything stays on your computer. Windows, with Python 3.11 and ffmpeg:

```bash
winget install Gyan.FFmpeg
```

```bash
py -3.11 -m venv .venv
```

```bash
.venv\Scripts\activate
```

```bash
pip install -e ".[dev]"
```

```bash
swingcheck
```

The app opens at `http://localhost:8765`. To use it from your phone on the same
Wi-Fi, start it with `swingcheck --phone` and open the address it prints (allow
Python through the firewall on private networks). Other options: `--port`,
`--no-browser`, and `--runs-dir`.

The first analysis downloads the pose model (about 30 MB); after that it works
offline. Ranges can be tuned in `config/local.toml`; see
[docs/development.md](docs/development.md#tuning).

## Troubleshooting

| Problem | What to do |
|---|---|
| Warning that a slo-mo clip is 30 or 60 fps | Upload the original file from your phone's camera roll. |
| Wrong impact frame | On the results page, open **Impact frame** and adjust it. |
| A check says "Not measured" | A body point wasn't tracked: usually lighting, the body out of frame, or baggy clothing. |
| A practice swing was found instead | **Edit marks**, then **Trim the clip**. |
| `ffmpeg not found` (running locally) | Install ffmpeg, open a new terminal, and start the app again. |
| Phone can't open the app (running locally) | Use `swingcheck --phone`, the same Wi-Fi, and allow Python through the firewall. |

## Documentation

- [User guide](docs/user-guide.md): filming, marking, and the results page, step by step.
- [Checkpoints and ranges](docs/checkpoints.md): what each checkpoint measures,
  its ranges, and how results are read.
- [Hosting and operations](docs/hosting.md): the server, limits, privacy model,
  and admin page.
- [Development](docs/development.md): tests, releases, tuning, and adding a check.
- [Release notes](docs/releases/): one PDF per release.

Built with Python, OpenCV, MediaPipe Pose, and ffmpeg.

## Support SwingCheck

SwingCheck is free. If it helps your game, you can
[support it on Ko-fi](https://ko-fi.com/jeromegarcia) to help cover the server
and upkeep costs. Thank you!

[![Support me on Ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/jeromegarcia)

In the Philippines? Support with InstaPay: scan this with GCash, Maya, or your banking app.

<img src="swingcheck/app/static/support/instapay-qr.png" alt="InstaPay QR code" width="200">
