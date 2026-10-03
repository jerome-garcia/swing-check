"""Start the app: `python -m swingcheck.app` (or `swingcheck`)."""

from __future__ import annotations

import argparse
import socket
import threading
import webbrowser
from pathlib import Path

import uvicorn

from swingcheck.app.server import create_app


def _lan_address() -> str | None:
    """This PC's address on the local network (no traffic is sent)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.168.0.1", 9))
            return s.getsockname()[0]
    except OSError:
        return None


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="swingcheck", description="Start the swing-check app.")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--phone", action="store_true",
                        help="also allow devices on your Wi-Fi (e.g. your iPhone) to open the app; there is no login")
    parser.add_argument("--no-browser", action="store_true", help="don't open a browser tab")
    parser.add_argument("--runs-dir", type=Path, help="where swings are stored (default: runs/ in the project)")
    args = parser.parse_args(argv)

    host = "0.0.0.0" if args.phone else "127.0.0.1"
    url = f"http://localhost:{args.port}"
    print(f"swing-check is running at {url}")
    if args.phone:
        lan = _lan_address()
        print(f"On your phone (same Wi-Fi), open: http://{lan or '<this PC IP>'}:{args.port}")
        print("Anyone on this Wi-Fi can open it while it's running. Stop with Ctrl+C.")
    else:
        print("Stop with Ctrl+C. Add --phone to open it from your phone on the same Wi-Fi.")
    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    uvicorn.run(create_app(args.runs_dir), host=host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
