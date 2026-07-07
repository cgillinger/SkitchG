"""Colors, sizes and shared constants for SkitchG."""

from PySide6.QtGui import QColor

# Skitch-style strong pink as default — visible on nearly any background.
DEFAULT_COLOR = QColor("#F5286E")

PALETTE = [
    ("Pink", QColor("#F5286E")),
    ("Red", QColor("#E8272C")),
    ("Orange", QColor("#F7941E")),
    ("Yellow", QColor("#FFD400")),
    ("Green", QColor("#39B54A")),
    ("Blue", QColor("#1E8FE1")),
    ("White", QColor("#FFFFFF")),
    ("Black", QColor("#1A1A1A")),
]

# Stroke widths (px in image coordinates, scaled by image resolution).
# The scale tops out where the old "Medium" was — that proved big enough.
STROKE_SIZES = {
    "XS": 2.5,
    "S": 4.0,
    "M": 6.0,
    "L": 10.0,
}
DEFAULT_STROKE = "M"

# Text point sizes tied to the size choice
TEXT_SIZES = {
    "XS": 14,
    "S": 18,
    "M": 23,
    "L": 34,
}

# Numbered marker head radius tied to the size choice
MARKER_RADII = {
    "XS": 11.0,
    "S": 14.0,
    "M": 17.0,
    "L": 24.0,
}

OUTLINE_COLOR = QColor("#FFFFFF")
SHADOW_COLOR = QColor(0, 0, 0, 110)

# Canvas background around the image
CANVAS_BG = QColor("#3A3D40")
