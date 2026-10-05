#!/usr/bin/env bash
# Release SwingCheck to the server. Run from the repo (Git Bash on Windows is fine).
#
#   deploy/deploy.sh                 what's live, and the latest releases
#   deploy/deploy.sh v0.2.0-alpha    release: a new tag is made on main (which must be clean
#                                    and pushed) and pushed; an existing tag is deployed as is,
#                                    so rolling back = deploying the previous tag
#
# On the server it waits until no analysis is running (a restart loses running jobs), checks
# the tag out, reinstalls the package if pyproject.toml changed, restarts and checks the site.
# New system packages (apt) still have to be installed by hand: see the README.
set -euo pipefail

HOST="${SWINGCHECK_HOST:-root@2.28.232.181}"
SITE="${SWINGCHECK_SITE:-https://swingcheck.org}"
TAG="${1:-}"

die() { echo "deploy: $*" >&2; exit 1; }
cd "$(git rev-parse --show-toplevel)"
git fetch -q --tags origin

if [ -z "$TAG" ]; then
  echo "Live on $SITE: $(ssh "$HOST" 'sudo -u swingcheck git -C /opt/swingcheck/app describe --tags --always')"
  echo "Latest releases:"; git tag --sort=-creatordate | head -5 | sed 's/^/  /'
  exit 0
fi
[[ "$TAG" =~ ^v[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.]+)?$ ]] || die "tags look like v0.2.0 or v0.2.0-alpha, not '$TAG'"

if ! git rev-parse -q --verify "refs/tags/$TAG" >/dev/null; then
  [ "$(git branch --show-current)" = main ] || die "new releases are tagged on main: git switch main"
  [ -z "$(git status --porcelain)" ] || die "uncommitted changes: commit or stash them first"
  [ "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)" ] || die "main differs from GitHub's: push (or pull) first"
  git tag -a "$TAG" -m "SwingCheck $TAG"
  echo "Tagged $(git rev-parse --short HEAD) as $TAG."
fi
git ls-remote --exit-code --tags origin "refs/tags/$TAG" >/dev/null || git push -q origin "$TAG"

# $TAG is checked above (letters, digits, dots, dashes), so it's safe inside the remote script.
ssh "$HOST" "TAG=$TAG bash -s" <<'REMOTE'
set -euo pipefail
APP=/opt/swingcheck/app
as_app() { sudo -u swingcheck "$@"; }
jobs_running() {  # "?" if the running version has no /api/health
  curl -sf http://127.0.0.1:8765/api/health | python3 -c 'import json,sys; print(json.load(sys.stdin)["jobs"])' 2>/dev/null || echo "?"
}

as_app git -C "$APP" fetch -q --tags origin
before=$(as_app git -C "$APP" rev-parse HEAD)
after=$(as_app git -C "$APP" rev-parse "$TAG^{commit}")
if [ "$before" = "$after" ]; then echo "The server already runs $TAG."; exit 0; fi

for i in $(seq 1 60); do  # up to 10 minutes
  n=$(jobs_running)
  { [ "$n" = 0 ] || [ "$n" = "?" ]; } && break
  [ "$i" = 1 ] && echo "Waiting for $n running analysis job(s) to finish…"
  sleep 10
done

as_app git -C "$APP" -c advice.detachedHead=false checkout -q "$TAG"
if ! as_app git -C "$APP" diff --quiet "$before" "$after" -- pyproject.toml; then
  echo "pyproject.toml changed: reinstalling…"
  as_app bash -lc 'cd ~/app && VIRTUAL_ENV=~/venv ~/.local/bin/uv pip install -q -e .'
fi
systemctl restart swingcheck

for i in $(seq 1 30); do
  [ "$(jobs_running)" != "?" ] && { echo "Server: $TAG is running."; exit 0; }
  sleep 1
done
echo "SwingCheck didn't come back up. Recent log:" >&2
journalctl -u swingcheck -n 30 --no-pager >&2
exit 1
REMOTE

health=$(curl -sf "$SITE/api/health") || die "$SITE didn't answer through Cloudflare"
live=$(printf '%s' "$health" | grep -o '"version":"[^"]*"' | cut -d'"' -f4 || true)
[ "$live" = "$TAG" ] || die "$SITE reports version '${live:-none}', not $TAG"
echo "Live: $SITE is on $TAG."
