#!/usr/bin/env bash
# Install SkitchG desktop integration for the current user.
set -euo pipefail

DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
BIN_DIR="$HOME/.local/bin"
APP_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor/512x512/apps"

mkdir -p "$BIN_DIR" "$APP_DIR" "$ICON_DIR"

ln -sf "$DIR/skitchg-launcher.sh" "$BIN_DIR/skitchg"
ln -sf "$DIR/skitchg-screenshot.sh" "$BIN_DIR/skitchg-screenshot"

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

sed -e "s|^Exec=skitchg-screenshot|Exec=$BIN_DIR/skitchg-screenshot|" \
    -e "s|^Icon=skitchg$|Icon=$DIR/icons/draw.png|" \
    "$DIR/skitchg-screenshot.desktop" > "$APP_DIR/skitchg-screenshot.desktop"

update-desktop-database "$APP_DIR" 2>/dev/null || true
gtk-update-icon-cache "$HOME/.local/share/icons/hicolor" 2>/dev/null || true

echo "Installed. Run 'skitchg image.jpg' or find SkitchG in the menu."
echo "Right-click an image -> Open With -> SkitchG should now be available."

# KDE Plasma: hand Print and Meta+Shift+S from Spectacle to SkitchG, so a
# screenshot opens straight in SkitchG. Spectacle keeps its other keys
# (Shift+Print, Meta+Print, ...) and its menu entry.
# Written to the config (survives logins) and pushed to the running session.
if [ "${XDG_CURRENT_DESKTOP:-}" = KDE ] && command -v kwriteconfig6 >/dev/null 2>&1; then
    set_key() {
        kwriteconfig6 --file kglobalshortcutsrc --group services --group "$1" --key _launch "$2"
    }
    set_key org.kde.spectacle.desktop "none"
    set_key skitchg-screenshot.desktop "Print"$'\t'"Meta+Shift+S"
    if command -v busctl >/dev/null 2>&1; then
        PRINT=16777225                                  # Qt::Key_Print
        META_SHIFT_S=$((0x10000000 | 0x02000000 | 0x53))
        accel() { busctl --user call org.kde.kglobalaccel /kglobalaccel org.kde.KGlobalAccel "$@" >/dev/null; }
        live() {  # component friendly-name key-count keys...
            local comp=$1 name=$2 n=$3; shift 3
            local seqs=()
            for k in "$@"; do seqs+=(4 "$k" 0 0 0); done
            accel doRegister as 4 "$comp" _launch "$name" "$name" &&
            accel setShortcutKeys "asa(ai)u" 4 "$comp" _launch "$name" "$name" "$n" "${seqs[@]}" 0x6
        }
        live org.kde.spectacle.desktop Spectacle 0 &&
            live skitchg-screenshot.desktop "SkitchG Screenshot" 2 "$PRINT" "$META_SHIFT_S" ||
            echo "Shortcut takes effect after logging out and in again."
    fi
    echo "Print and Meta+Shift+S now open a region screenshot in SkitchG."
fi
