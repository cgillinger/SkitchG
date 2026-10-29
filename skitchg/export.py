"""Rendering the annotated image for save/copy/export."""

import shutil
import subprocess

from PySide6.QtCore import QBuffer, QIODevice, QRectF
from PySide6.QtGui import QGuiApplication, QImage, QPainter

WL_COPY_TIMEOUT = 5  # seconds


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


def _png_bytes(image):
    buffer = QBuffer()
    buffer.open(QIODevice.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(buffer.data())


def _copy_with_wl_copy(image):
    """Hand the image to wl-copy, which keeps serving it from its own process.

    Qt's own Wayland clipboard tags the selection with the serial of the
    app's last input event, and KWin silently drops a selection whose serial
    is older than the current owner's (e.g. one set by Klipper or another
    app since). Qt's copy also vanishes when SkitchG quits. wl-copy avoids
    both.
    """
    if shutil.which("wl-copy") is None:
        return False
    try:
        # wl-copy forks a background server and the parent exits; DEVNULL
        # keeps that server from holding our pipes open.
        subprocess.run(["wl-copy", "--type", "image/png"], input=_png_bytes(image),
                       timeout=WL_COPY_TIMEOUT, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (subprocess.SubprocessError, OSError):
        return False
    return True


def copy_image(image):
    """Put the image on the system clipboard."""
    if QGuiApplication.platformName() == "wayland" and _copy_with_wl_copy(image):
        return
    QGuiApplication.clipboard().setImage(image)
