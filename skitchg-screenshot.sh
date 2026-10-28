#!/usr/bin/env bash
# Take a screenshot and open it straight in SkitchG: skitchg-screenshot [mode]
#
# mode: region (default), full, window, monitor. KDE uses Spectacle in
# background mode; elsewhere grim+slurp (Wayland) or gnome-screenshot.
# The capture is kept next to Spectacle's own screenshots, so nothing is
# lost if SkitchG is closed without saving.
set -euo pipefail

DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
MODE="${1:-region}"

PICTURES="$(xdg-user-dir PICTURES 2>/dev/null || echo "$HOME/Pictures")"
OUT_DIR="$PICTURES/Screenshots"
[ -d "$PICTURES/Skärmbilder" ] && OUT_DIR="$PICTURES/Skärmbilder"
mkdir -p "$OUT_DIR"
OUT="$OUT_DIR/Screenshot_$(date +%Y%m%d_%H%M%S).png"

if command -v spectacle >/dev/null 2>&1; then
    case "$MODE" in
        full)    flag=-f ;;
        window)  flag=-a ;;
        monitor) flag=-m ;;
        *)       flag=-r ;;
    esac
    spectacle -b -n "$flag" -o "$OUT"
elif command -v grim >/dev/null 2>&1; then
    if [ "$MODE" = full ]; then grim "$OUT"; else grim -g "$(slurp)" "$OUT"; fi
elif command -v gnome-screenshot >/dev/null 2>&1; then
    case "$MODE" in
        full)   gnome-screenshot -f "$OUT" ;;
        window) gnome-screenshot -w -f "$OUT" ;;
        *)      gnome-screenshot -a -f "$OUT" ;;
    esac
else
    echo "SkitchG: no screenshot tool found (spectacle, grim or gnome-screenshot)." >&2
    exit 1
fi

# Escape in the region picker leaves no file: just quit quietly.
[ -s "$OUT" ] || exit 0
exec "$DIR/skitchg-launcher.sh" "$OUT"
