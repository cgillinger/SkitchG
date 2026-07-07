#!/usr/bin/env bash
# Launch SkitchG from anywhere: skitchg [image.jpg]
DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
exec "$DIR/.venv/bin/python" "$DIR/app.py" "$@"
