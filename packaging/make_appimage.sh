#!/usr/bin/env bash
# Builds dist/PushuuuLauncher-<version>-<arch>.AppImage from the PyInstaller folder dist/PushuuuLauncher
# Set APPIMAGETOOL=/path/to/appimagetool to skip the download.
set -euo pipefail
cd "$(dirname "$0")/.."
VER="$(python3 -c 'import pushuuu_core as c; print(c.APP_VERSION)')"
ARCH="$(uname -m)"
SRC="dist/PushuuuLauncher"
[ -d "$SRC" ] || { echo "Missing $SRC - run PyInstaller first" >&2; exit 1; }

APPDIR="$(mktemp -d)/PushuuuLauncher.AppDir"
mkdir -p "$APPDIR/usr/bin"
cp -r "$SRC"/. "$APPDIR/usr/bin/"
cp packaging/pushuuu-launcher.desktop "$APPDIR/pushuuu-launcher.desktop"
cp packaging/icon.png "$APPDIR/pushuuu-launcher.png"
ln -s pushuuu-launcher.png "$APPDIR/.DirIcon"
cat > "$APPDIR/AppRun" << 'RUN'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/PushuuuLauncher" "$@"
RUN
chmod +x "$APPDIR/AppRun" "$APPDIR/usr/bin/PushuuuLauncher"

TOOL="${APPIMAGETOOL:-}"
if [ -z "$TOOL" ]; then
  TOOL="$(mktemp -d)/appimagetool"
  curl -fsSL -o "$TOOL" "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-${ARCH}.AppImage"
  chmod +x "$TOOL"
fi
mkdir -p dist
# --appimage-extract-and-run: CI runners have no FUSE
ARCH="$ARCH" "$TOOL" --appimage-extract-and-run "$APPDIR" "dist/PushuuuLauncher-${VER}-${ARCH}.AppImage"
