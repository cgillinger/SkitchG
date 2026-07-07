#!/usr/bin/env python3
"""SkitchG entry point.

Usage:
    skitchg [image.jpg]
"""

import sys

from PySide6.QtWidgets import QApplication

from skitchg.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("SkitchG")
    app.setOrganizationName("SkitchG")

    window = MainWindow()
    window.show()

    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if args:
        window.load_file(args[0], confirm=False)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
