"""Windows tray helper: a global hotkey and tray icon that start a capture."""

import sys

import os

from PySide6.QtCore import QAbstractNativeEventFilter, QDir, QLockFile, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from .capture import capture_to_file
from .main_window import MainWindow

WM_HOTKEY = 0x0312
WM_KEYUP = 0x0101
WM_SYSKEYUP = 0x0105
WH_KEYBOARD_LL = 13
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_NOREPEAT = 0x4000
VK_SNAPSHOT = 0x2C  # Print Screen

# Both are registered; Ctrl+Alt+S always works as a second key.
HOTKEYS = [
    (1, "Print Screen", 0, VK_SNAPSHOT),
    (2, "Ctrl+Alt+S", MOD_CONTROL | MOD_ALT, ord("S")),
]
HOTKEY_IDS = {hotkey_id for hotkey_id, *_ in HOTKEYS}


class PrintScreenHook:
    """Low-level keyboard hook that takes Print Screen before Windows does.

    RegisterHotKey is refused while Windows' "Use the Print screen button to
    open screen capturing" setting is on (the default). A WH_KEYBOARD_LL hook
    sees the key first and can swallow it, so the Snipping Tool never opens.
    """

    def __init__(self, callback):
        import ctypes
        from ctypes import wintypes

        class KBDLLHOOKSTRUCT(ctypes.Structure):
            _fields_ = [("vkCode", wintypes.DWORD), ("scanCode", wintypes.DWORD),
                        ("flags", wintypes.DWORD), ("time", wintypes.DWORD),
                        ("dwExtraInfo", ctypes.c_size_t)]

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        proc_type = ctypes.WINFUNCTYPE(wintypes.LPARAM, ctypes.c_int,
                                       wintypes.WPARAM, wintypes.LPARAM)
        user32.SetWindowsHookExW.argtypes = (ctypes.c_int, proc_type,
                                             wintypes.HINSTANCE, wintypes.DWORD)
        user32.SetWindowsHookExW.restype = wintypes.HHOOK
        user32.CallNextHookEx.argtypes = (wintypes.HHOOK, ctypes.c_int,
                                          wintypes.WPARAM, wintypes.LPARAM)
        user32.CallNextHookEx.restype = wintypes.LPARAM
        user32.UnhookWindowsHookEx.argtypes = (wintypes.HHOOK,)
        kernel32.GetModuleHandleW.restype = wintypes.HMODULE

        def hook(n_code, w_param, l_param):
            if n_code == 0:
                info = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                if info.vkCode == VK_SNAPSHOT:
                    # Fire on release (Print Screen may not send a key-down)
                    # and keep the hook fast: Windows drops slow hooks.
                    if w_param in (WM_KEYUP, WM_SYSKEYUP):
                        QTimer.singleShot(0, callback)
                    return 1  # swallow both down and up
            return user32.CallNextHookEx(None, n_code, w_param, l_param)

        self._user32 = user32
        self._proc = proc_type(hook)  # must outlive the hook
        self._handle = user32.SetWindowsHookExW(
            WH_KEYBOARD_LL, self._proc, kernel32.GetModuleHandleW(None), 0)

    @property
    def active(self):
        return bool(self._handle)

    def remove(self):
        if self._handle:
            self._user32.UnhookWindowsHookEx(self._handle)
            self._handle = None


class HotkeyFilter(QAbstractNativeEventFilter):
    def __init__(self, callback):
        super().__init__()
        self._callback = callback

    def nativeEventFilter(self, event_type, message):
        if sys.platform == "win32" and bytes(event_type) == b"windows_generic_MSG":
            import ctypes.wintypes
            msg = ctypes.wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY and msg.wParam in HOTKEY_IDS:
                # Return to the event loop first; the capture runs its own UI.
                QTimer.singleShot(0, self._callback)
                return True, 0
        return False, 0


def already_running():
    """True when another tray helper holds the lock (two would each grab
    Print Screen and take every screenshot twice)."""
    lock = QLockFile(os.path.join(QDir.tempPath(), "skitchg-tray.lock"))
    if not lock.tryLock(100):
        return True
    already_running.lock = lock  # held until the process exits
    return False


class Tray:
    def __init__(self, app):
        self._windows = []
        self._hotkeys = []  # names of the active hotkeys
        self._registered = []
        self._hook = None

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

        hint = (f"Press {' or '.join(self._hotkeys)} to take a screenshot"
                if self._hotkeys else "No global hotkey could be registered - use the menu")
        self.icon.setToolTip(f"SkitchG - {hint}")
        self.icon.show()

    def _register_hotkey(self):
        if sys.platform != "win32":
            return
        import ctypes
        for hotkey_id, name, mods, vk in HOTKEYS:
            if ctypes.windll.user32.RegisterHotKey(None, hotkey_id, MOD_NOREPEAT | mods, vk):
                self._registered.append(hotkey_id)
                self._hotkeys.append(name)
            elif vk == VK_SNAPSHOT:
                # Windows keeps Print Screen for the Snipping Tool: take it
                # with a keyboard hook instead.
                self._hook = PrintScreenHook(self.take_screenshot)
                if self._hook.active:
                    self._hotkeys.append(name)

    def _unregister_hotkey(self):
        if sys.platform != "win32":
            return
        import ctypes
        for hotkey_id in self._registered:
            ctypes.windll.user32.UnregisterHotKey(None, hotkey_id)
        self._registered = []
        if self._hook is not None:
            self._hook.remove()
            self._hook = None

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
