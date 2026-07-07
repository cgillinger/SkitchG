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

# Stroke widths (px in image coordinates)
STROKE_SIZES = {
    "Small": 4.0,
    "Medium": 8.0,
    "Large": 14.0,
}
DEFAULT_STROKE = "Medium"

# Text point sizes tied to stroke size choice
TEXT_SIZES = {
    "Small": 20,
    "Medium": 28,
    "Large": 40,
}

OUTLINE_COLOR = QColor("#FFFFFF")
SHADOW_COLOR = QColor(0, 0, 0, 110)

# Canvas background around the image
CANVAS_BG = QColor("#3A3D40")
