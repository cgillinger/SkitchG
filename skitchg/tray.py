"""Windows tray helper: a global hotkey and tray icon that start a capture."""

import sys

from PySide6.QtCore import QAbstractNativeEventFilter, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from .capture import capture_to_file
from .main_window import MainWindow

WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_NOREPEAT = 0x4000
VK_SNAPSHOT = 0x2C  # Print Screen

HOTKEY_ID = 1
# PrintScreen is refused while Windows' "Use Print screen to open Snipping
# Tool" is on, so Ctrl+Alt+S is the fallback.
HOTKEYS = [
    ("Print Screen", 0, VK_SNAPSHOT),
    ("Ctrl+Alt+S", MOD_CONTROL | MOD_ALT, ord("S")),
]


class HotkeyFilter(QAbstractNativeEventFilter):
    def __init__(self, callback):
        super().__init__()
        self._callback = callback

    def nativeEventFilter(self, event_type, message):
        if sys.platform == "win32" and bytes(event_type) == b"windows_generic_MSG":
            import ctypes.wintypes
            msg = ctypes.wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                # Return to the event loop first; the capture runs its own UI.
                QTimer.singleShot(0, self._callback)
                return True, 0
        return False, 0


class Tray:
    def __init__(self, app):
        self._windows = []
        self._hotkey_name = None

        self.icon = QSystemTrayIcon(app.windowIcon())
        menu = QMenu()
        for label, fn in [("Take screenshot", self.take_screenshot),
                          ("Open SkitchG", self.open_window),
                          ("Quit", app.quit)]:
            action = QAction(label, menu)
            action.triggered.connect(fn)
            menu.addAction(action)
        self.icon.setContextMenu(menu)
        self.icon.activated.connect(self._on_activated)
        self._menu = menu  # the tray icon does not take ownership

        self._filter = HotkeyFilter(self.take_screenshot)
        app.installNativeEventFilter(self._filter)
        self._register_hotkey()
        app.aboutToQuit.connect(self._unregister_hotkey)

        hint = (f"Press {self._hotkey_name} to take a screenshot" if self._hotkey_name
                else "No global hotkey could be registered - use the menu")
        self.icon.setToolTip(f"SkitchG - {hint}")
        self.icon.show()

    def _register_hotkey(self):
        if sys.platform != "win32":
            return
        import ctypes
        for name, mods, vk in HOTKEYS:
            if ctypes.windll.user32.RegisterHotKey(None, HOTKEY_ID, MOD_NOREPEAT | mods, vk):
                self._hotkey_name = name
                return

    def _unregister_hotkey(self):
        if sys.platform == "win32" and self._hotkey_name:
            import ctypes
            ctypes.windll.user32.UnregisterHotKey(None, HOTKEY_ID)
            self._hotkey_name = None

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:  # left-click
            self.take_screenshot()

    def take_screenshot(self):
        capture_to_file(self._screenshot_done)

    def _screenshot_done(self, path, ok):
        if path:
            self.open_window(path)

    def open_window(self, path=None):
        window = MainWindow()
        # Closed windows stay referenced only until the next one opens.
        self._windows = [w for w in self._windows if w.isVisible()] + [window]
        if path:
            window.load_file(path, confirm=False)
        window.show()
        window.raise_()
        window.activateWindow()
