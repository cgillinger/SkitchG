#!/usr/bin/env bash
# Install SkitchG desktop integration for the current user.
set -euo pipefail

DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
BIN_DIR="$HOME/.local/bin"
APP_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor/512x512/apps"

mkdir -p "$BIN_DIR" "$APP_DIR" "$ICON_DIR"

ln -sf "$DIR/skitchg-launcher.sh" "$BIN_DIR/skitchg"

# Icon: install into hicolor at common sizes AND reference it by absolute
# path in the .desktop file — menus pick up the absolute path immediately,
# without waiting for an icon-cache refresh.
cp "$DIR/icons/draw.png" "$ICON_DIR/skitchg.png"
for size in 48 128 256; do
    dir="$HOME/.local/share/icons/hicolor/${size}x${size}/apps"
    mkdir -p "$dir"
    cp "$DIR/icons/draw.png" "$dir/skitchg.png"
done

sed -e "s|^Exec=skitchg|Exec=$BIN_DIR/skitchg|" \
    -e "s|^Icon=skitchg$|Icon=$DIR/icons/draw.png|" \
    "$DIR/skitchg.desktop" > "$APP_DIR/skitchg.desktop"

update-desktop-database "$APP_DIR" 2>/dev/null || true
gtk-update-icon-cache "$HOME/.local/share/icons/hicolor" 2>/dev/null || true

echo "Installed. Run 'skitchg image.jpg' or find SkitchG in the menu."
echo "Right-click an image -> Open With -> SkitchG should now be available."
