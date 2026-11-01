#!/usr/bin/env bash
# Builds dist/pushuuu-launcher_<version>_<arch>.deb from the PyInstaller folder dist/PushuuuLauncher
set -euo pipefail
cd "$(dirname "$0")/.."
VER="$(python3 -c 'import pushuuu_core as c; print(c.APP_VERSION)')"
ARCH="$(dpkg --print-architecture)"
SRC="dist/PushuuuLauncher"
[ -d "$SRC" ] || { echo "Missing $SRC - run PyInstaller first" >&2; exit 1; }

PKG="$(mktemp -d)/pushuuu-launcher_${VER}_${ARCH}"
mkdir -p "$PKG/DEBIAN" "$PKG/opt/pushuuu-launcher" "$PKG/usr/bin" \
         "$PKG/usr/share/applications" "$PKG/usr/share/icons/hicolor/512x512/apps"
cp -r "$SRC"/. "$PKG/opt/pushuuu-launcher/"
ln -s /opt/pushuuu-launcher/PushuuuLauncher "$PKG/usr/bin/pushuuu-launcher"
sed 's|^Exec=.*|Exec=/opt/pushuuu-launcher/PushuuuLauncher|' packaging/pushuuu-launcher.desktop \
    > "$PKG/usr/share/applications/pushuuu-launcher.desktop"
cp packaging/icon.png "$PKG/usr/share/icons/hicolor/512x512/apps/pushuuu-launcher.png"

cat > "$PKG/DEBIAN/control" << CONTROL
Package: pushuuu-launcher
Version: ${VER}
Section: games
Priority: optional
Architecture: ${ARCH}
Installed-Size: $(du -sk "$PKG" | cut -f1)
Maintainer: Pushuuu <pushuuu@users.noreply.github.com>
Description: Minecraft launcher with mod support
 Every Minecraft version, instances, Fabric/Quilt/Forge/NeoForge
 and a built-in Modrinth browser for mods, packs and shaders.
CONTROL

find "$PKG" -type d -exec chmod 755 {} +
chmod 755 "$PKG/opt/pushuuu-launcher/PushuuuLauncher"
mkdir -p dist
dpkg-deb --build --root-owner-group "$PKG" "dist/pushuuu-launcher_${VER}_${ARCH}.deb"
