#!/usr/bin/env python3
"""SkitchG entry point.

Usage:
    skitchg [image.jpg]
    skitchg --capture    take a screenshot, then open it
    skitchg --tray       tray icon + global hotkey (Windows)
"""

import os
import sys

from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from skitchg.capture import capture_to_file
from skitchg.main_window import MainWindow

# Bundled data lives in sys._MEIPASS in a PyInstaller build.
BASE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
ICON_PATH = os.path.join(BASE_DIR, "icons", "draw.png")


def run_capture(app):
    windows = []  # keeps the window alive

    def done(path, ok):
        if path is None:
            app.exit(0 if ok else 1)
            return
        window = MainWindow()
        windows.append(window)
        window.load_file(path, confirm=False)
        window.show()
        window.raise_()
        window.activateWindow()
        app.setQuitOnLastWindowClosed(True)

    # The overlays close before the main window exists, which would
    # otherwise count as "last window closed".
    app.setQuitOnLastWindowClosed(False)
    QTimer.singleShot(0, lambda: capture_to_file(done))


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("SkitchG")
    app.setOrganizationName("SkitchG")
    app.setWindowIcon(QIcon(ICON_PATH))

    if "--capture" in sys.argv:
        run_capture(app)
    elif "--tray" in sys.argv:
        from skitchg.tray import Tray, already_running
        if already_running():
            return
        app.setQuitOnLastWindowClosed(False)
        tray = Tray(app)  # noqa: F841 - must stay referenced
    else:
        window = MainWindow()
        window.show()
        args = [a for a in sys.argv[1:] if not a.startswith("-")]
        if args:
            window.load_file(args[0], confirm=False)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
