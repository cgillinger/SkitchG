"""Rendering the annotated image for save/copy/export."""

from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage, QPainter


def render_annotated(canvas):
    """Flatten base image + annotations into a new QImage at native resolution."""
    base = canvas.base_image()
    if base is None:
        return None
    canvas.commit_text_edit()
    canvas.scene().clearSelection()
    image = QImage(base.size(), QImage.Format_ARGB32_Premultiplied)
    image.fill(0)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
    source = QRectF(base.rect())
    canvas.scene().render(painter, QRectF(image.rect()), source)
    painter.end()
    return image
