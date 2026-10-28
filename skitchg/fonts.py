"""Shared UI font so Linux and Windows both get a sensible sans-serif."""

from PySide6.QtGui import QFont

# "Sans Serif" is a fontconfig alias that does not exist on Windows, where
# Qt would fall back to a serif face; the later families cover that case.
FAMILIES = ["Sans Serif", "Segoe UI", "Arial"]


def sans_font(point_size=None):
    font = QFont()
    font.setFamilies(FAMILIES)
    if point_size is not None:
        font.setPointSize(point_size)
    return font
