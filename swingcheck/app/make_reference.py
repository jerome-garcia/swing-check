"""Build the marking reference (Rory McIlroy) shipped with the app.

The marking screen shows these frames, with their marks, beside each step as an
example to follow. Rebuild them from a fully marked down-the-line swing with:

    python -m swingcheck.app.make_reference runs/<swing-folder> "Rory McIlroy"

"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from swingcheck.app.frames import FrameReader
from swingcheck.ingest import VideoInfo

OUT = Path(__file__).parent / "static" / "reference"
WIDTH = 480  # px; the marking screen shows it at up to 220 px wide


def build(run_dir: Path, name: str, out: Path = OUT) -> dict:
    info = VideoInfo.load(run_dir / "video.json")
    marks = json.loads((run_dir / "marks.json").read_text())
    steps = {"address": {"frame": marks["address_frame"], "points": marks["points"]}}
    steps.update(marks.get("checkpoints") or {})
    scale = min(1.0, WIDTH / info.width)
    out.mkdir(parents=True, exist_ok=True)
    reader = FrameReader()
    data = {"name": name, "width": round(info.width * scale), "height": round(info.height * scale), "steps": {}}
    for key, step in steps.items():
        image = f"{key}.jpg"
        (out / image).write_bytes(reader.jpeg(run_dir / "normalized.mp4", step["frame"], width=data["width"]))
        data["steps"][key] = {"image": image,
                              "points": {k: [round(x * scale, 1), round(y * scale, 1)] for k, (x, y) in step["points"].items()}}
    (out / "reference.json").write_text(json.dumps(data, indent=2))
    return data


if __name__ == "__main__":
    built = build(Path(sys.argv[1]), sys.argv[2] if len(sys.argv) > 2 else "Rory McIlroy")
    print(f"Wrote {len(built['steps'])} steps to {OUT}")
