#!/usr/bin/env bash
# Install SkitchG desktop integration for the current user.
set -euo pipefail

DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
BIN_DIR="$HOME/.local/bin"
APP_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor/512x512/apps"

mkdir -p "$BIN_DIR" "$APP_DIR" "$ICON_DIR"

ln -sf "$DIR/skitchg-launcher.sh" "$BIN_DIR/skitchg"
cp "$DIR/icons/draw.png" "$ICON_DIR/skitchg.png"

sed "s|^Exec=skitchg|Exec=$BIN_DIR/skitchg|" "$DIR/skitchg.desktop" \
    > "$APP_DIR/skitchg.desktop"

update-desktop-database "$APP_DIR" 2>/dev/null || true
gtk-update-icon-cache "$HOME/.local/share/icons/hicolor" 2>/dev/null || true

echo "Installed. Run 'skitchg image.jpg' or find SkitchG in the menu."
echo "Right-click an image -> Open With -> SkitchG should now be available."
