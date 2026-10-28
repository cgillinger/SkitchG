"""Screen capture backend plus the shared "capture, pick a region, save" flow."""

import os
import shutil
import subprocess
import tempfile
from datetime import datetime

from PySide6.QtCore import QRect, QStandardPaths
from PySide6.QtGui import QGuiApplication, QImage
from PySide6.QtWidgets import QMessageBox

from .snip import SnipSession

# Platforms where Qt can read the screen contents itself.
DIRECT_PLATFORMS = ("windows", "xcb", "cocoa")
TOOL_TIMEOUT = 15  # seconds

# The one active session (if any): keeps it alive and blocks double captures.
_active_session = None


def split_by_screens(image, rects):
    """Cut a whole-workspace image into one image per logical screen rect.

    The tools capture physical pixels while screen geometries are logical,
    so the scale is derived from the image/bounding-box width ratio.
    """
    if image.isNull() or not rects:
        return []
    bounding = rects[0]
    for r in rects[1:]:
        bounding = bounding.united(r)
    scale = image.width() / bounding.width()
    parts = []
    for r in rects:
        crop = QRect(round((r.x() - bounding.x()) * scale),
                     round((r.y() - bounding.y()) * scale),
                     round(r.width() * scale), round(r.height() * scale))
        parts.append(image.copy(crop.intersected(image.rect())))
    return parts


def _tool_commands(path):
    # Spectacle is authorized by KWin to capture on Wayland and shows no UI
    # in background mode; the others cover wlroots and GNOME.
    return [
        ("spectacle", ["spectacle", "-b", "-n", "-f", "-o", path]),
        ("grim", ["grim", path]),
        ("gnome-screenshot", ["gnome-screenshot", "-f", path]),
    ]


def _grab_with_tool():
    """Whole-workspace image from the first available external tool."""
    tmp = tempfile.mkdtemp(prefix="skitchg-capture-")
    try:
        path = os.path.join(tmp, "capture.png")
        for exe, cmd in _tool_commands(path):
            if shutil.which(exe) is None:
                continue
            try:
                subprocess.run(cmd, timeout=TOOL_TIMEOUT, check=True,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except (subprocess.SubprocessError, OSError):
                continue
            image = QImage(path)
            if not image.isNull():
                return image
        return QImage()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def grab_screens():
    """One frozen image per screen in physical pixels, [] on failure."""
    screens = QGuiApplication.screens()
    if QGuiApplication.platformName() in DIRECT_PLATFORMS:
        grabbed = [(s, s.grabWindow(0).toImage()) for s in screens]
        return [(s, i) for s, i in grabbed if not i.isNull()]
    image = _grab_with_tool()
    parts = split_by_screens(image, [s.geometry() for s in screens])
    return [(s, i) for s, i in zip(screens, parts) if not i.isNull()]


def screenshots_dir():
    pictures = QStandardPaths.writableLocation(QStandardPaths.PicturesLocation)
    if not pictures:
        pictures = os.path.expanduser("~/Pictures")
    # Swedish KDE/Spectacle uses "Skärmbilder"; reuse it so captures land
    # next to the user's existing screenshots.
    swedish = os.path.join(pictures, "Skärmbilder")
    path = swedish if os.path.isdir(swedish) else os.path.join(pictures, "Screenshots")
    os.makedirs(path, exist_ok=True)
    return path


def new_screenshot_path():
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(screenshots_dir(), f"Screenshot_{stamp}.png")


def capture_to_file(on_done):
    """Grab the screens, let the user pick a region, save it as a PNG.

    Calls on_done(path, ok): a saved file gives (path, True), a cancelled
    selection (None, True) and a failure (None, False). The PNG is written
    before any window opens so nothing is lost if the user closes
    SkitchG without saving.
    """
    global _active_session
    if _active_session is not None:
        return

    screens = grab_screens()
    if not screens:
        QMessageBox.critical(
            None, "SkitchG",
            "Could not capture the screen. No screenshot tool was found "
            "(on Linux with Wayland SkitchG needs spectacle, grim or "
            "gnome-screenshot).")
        on_done(None, False)
        return

    session = SnipSession(screens)
    _active_session = session

    def on_finished(image):
        global _active_session
        _active_session = None
        session.deleteLater()
        if image is None:
            on_done(None, True)
            return
        path = new_screenshot_path()
        if not image.save(path, "PNG"):
            QMessageBox.critical(None, "SkitchG", f"Could not save screenshot to:\n{path}")
            on_done(None, False)
            return
        on_done(path, True)

    session.finished.connect(on_finished)
    session.start()
