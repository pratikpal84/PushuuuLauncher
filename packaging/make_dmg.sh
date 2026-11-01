#!/usr/bin/env bash
# Builds dist/PushuuuLauncher-<version>-macOS-<label>.dmg from dist/PushuuuLauncher.app   (macOS only)
# usage: packaging/make_dmg.sh AppleSilicon|Intel
set -euo pipefail
cd "$(dirname "$0")/.."
LABEL="${1:-AppleSilicon}"
VER="$(python3 -c 'import pushuuu_core as c; print(c.APP_VERSION)')"
APP="dist/PushuuuLauncher.app"
[ -d "$APP" ] || { echo "Missing $APP - run PyInstaller first" >&2; exit 1; }

STAGE="$(mktemp -d)"
ditto "$APP" "$STAGE/PushuuuLauncher.app"      # ditto keeps symlinks, permissions and signatures intact
ln -s /Applications "$STAGE/Applications"      # the familiar "drag to Applications" window
OUT="dist/PushuuuLauncher-${VER}-macOS-${LABEL}.dmg"
hdiutil create -volname "Pushuuu Launcher" -srcfolder "$STAGE" -ov -format UDZO "$OUT"
echo "Built $OUT"
