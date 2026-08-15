#!/usr/bin/env bash
# Launch SkitchG from anywhere: skitchg [image.jpg]
#
# Self-heals the virtualenv: if .venv is missing, or was built against a
# Python that no longer exists (e.g. after a distro migration or OS upgrade
# changed the system Python version), it is rebuilt automatically before
# launching. Works the same on Mint/Ubuntu, Fedora, and other distros.
DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
VENV="$DIR/.venv"
PY="$VENV/bin/python"

venv_ok() {
    [ -x "$PY" ] && "$PY" -c "import PySide6" >/dev/null 2>&1
}

if ! venv_ok; then
    echo "SkitchG: rebuilding virtualenv for $(python3 --version 2>&1) (first launch after an OS/Python change)..." >&2
    rm -rf "$VENV"
    if ! python3 -m venv "$VENV"; then
        echo "SkitchG: could not create virtualenv." >&2
        echo "  Debian/Ubuntu/Mint: sudo apt install python3-venv" >&2
        exit 1
    fi
    if ! "$VENV/bin/pip" install --quiet -r "$DIR/requirements.txt"; then
        echo "SkitchG: failed to install dependencies (network down?)." >&2
        rm -rf "$VENV"   # leave no half-built venv behind
        exit 1
    fi
fi

exec "$PY" "$DIR/app.py" "$@"
