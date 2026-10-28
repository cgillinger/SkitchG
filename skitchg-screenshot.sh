#!/usr/bin/env bash
# skitchg-screenshot: take a screenshot and open it in SkitchG.
# Same as `skitchg --capture`; kept as its own command so the desktop
# shortcut's path stays stable across versions (KWin caches it).
DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
exec "$DIR/skitchg-launcher.sh" --capture "$@"
