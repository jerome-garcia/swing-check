#!/bin/sh
# Render branding/*.html to PNG at 2x with headless Edge (Windows, Git Bash).
#   sh branding/render.sh            -> branding/ko-fi-cover.png (3000x1000)
cd "$(dirname "$0")"
EDGE="/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
"$EDGE" --headless --disable-gpu --hide-scrollbars --force-device-scale-factor=2 \
  --window-size=1500,500 --screenshot="$(pwd -W)/ko-fi-cover.png" "file:///$(pwd -W)/ko-fi-cover.html"
