#!/bin/sh
# Render the branding pages with headless Edge (Windows, Git Bash):
#   sh branding/render.sh
#     -> branding/ko-fi-cover.png              (3000x1000)
#     -> branding/swingcheck-brand-guide.pdf   (one A4 page)
#     -> branding/swingcheck-brand-guide.png   (preview of the PDF)
#     -> swingcheck/app/static/og-image.png    (link preview, 1200x630)
cd "$(dirname "$0")"
EDGE="/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
HERE="$(pwd -W)"
"$EDGE" --headless --disable-gpu --hide-scrollbars --force-device-scale-factor=2 \
  --window-size=1500,500 --screenshot="$HERE/ko-fi-cover.png" "file:///$HERE/ko-fi-cover.html"
"$EDGE" --headless --disable-gpu --no-pdf-header-footer \
  --print-to-pdf="$HERE/swingcheck-brand-guide.pdf" "file:///$HERE/brand-guide.html"
"$EDGE" --headless --disable-gpu --hide-scrollbars --force-device-scale-factor=2 \
  --window-size=794,1123 --screenshot="$HERE/swingcheck-brand-guide.png" "file:///$HERE/brand-guide.html"
"$EDGE" --headless --disable-gpu --hide-scrollbars --force-device-scale-factor=1   --window-size=1200,630 --screenshot="$(cd ../swingcheck/app/static && pwd -W)/og-image.png" "file:///$HERE/link-preview.html"
