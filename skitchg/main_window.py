"""SkitchG main window: toolbars, menus, open/save/copy."""

import os

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QGuiApplication,
    QImage,
    QImageReader,
    QKeySequence,
)
from PySide6.QtWidgets import (
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QToolBar,
    QToolButton,
)

from .canvas import Canvas
from .export import render_annotated
from .icons import make_color_icon, make_icon
from .palette import DEFAULT_STROKE, PALETTE, STROKE_SIZES

IMAGE_FILTER = "Images (*.png *.jpg *.jpeg *.webp *.bmp);;All files (*)"

TOOLS = [
    ("select", "Select / Move", "V"),
    ("arrow", "Arrow", "A"),
    ("line", "Line", "L"),
    ("rect", "Rectangle", "R"),
    ("ellipse", "Ellipse", "E"),
    ("pen", "Pen", "P"),
    ("text", "Text", "T"),
    ("pixelate", "Pixelate", "X"),
    ("crop", "Crop", "C"),
]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SkitchG")
        self.resize(1100, 750)

        self.canvas = Canvas(self)
        self.setCentralWidget(self.canvas)
        self.canvas.dirty_changed.connect(self._update_title)
        self.canvas.tool_changed.connect(self._sync_tool_buttons)
        self.canvas.undo_stack.cleanChanged.connect(self._update_title)

        self.source_path = None   # the opened original file
        self.save_path = None     # where Save writes (never original by default)

        self._icon_color = self.palette().windowText().color()
        self._build_tool_bar()
        self._build_top_bar()
        self._build_menus()
        self.setAcceptDrops(True)
        self.statusBar().showMessage(
            "Open an image (Ctrl+O) or drop one here — then drag an arrow and Ctrl+C.")
        self.canvas.set_tool("arrow")

    # ------------------------------------------------------------------ UI

    def _build_tool_bar(self):
        bar = QToolBar("Tools", self)
        bar.setOrientation(Qt.Vertical)
        bar.setMovable(False)
        bar.setIconSize(QSize(26, 26))
        self.addToolBar(Qt.LeftToolBarArea, bar)

        self._tool_actions = {}
        group = QActionGroup(self)
        group.setExclusive(True)
        for name, label, key in TOOLS:
            # Tool keys (A, T, R…) are handled by the canvas so they never
            # steal keystrokes while typing a text annotation.
            action = QAction(make_icon(name, self._icon_color), label, self)
            action.setCheckable(True)
            action.setToolTip(f"{label} ({key})")
            action.triggered.connect(lambda checked, n=name: self.canvas.set_tool(n))
            group.addAction(action)
            bar.addAction(action)
            self._tool_actions[name] = action
        self._tool_actions["arrow"].setChecked(True)

    def _build_top_bar(self):
        bar = QToolBar("Actions", self)
        bar.setMovable(False)
        bar.setIconSize(QSize(22, 22))
        self.addToolBar(Qt.TopToolBarArea, bar)

        self.open_action = QAction("Open", self)
        self.open_action.setShortcut(QKeySequence.Open)
        self.open_action.triggered.connect(self.open_dialog)
        bar.addAction(self.open_action)

        self.save_action = QAction("Save", self)
        self.save_action.setShortcut(QKeySequence.Save)
        self.save_action.triggered.connect(self.save)
        bar.addAction(self.save_action)

        self.save_as_action = QAction("Save As…", self)
        self.save_as_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self.save_as_action.triggered.connect(self.save_as)
        bar.addAction(self.save_as_action)

        self.copy_action = QAction("Copy", self)
        self.copy_action.setShortcut(QKeySequence.Copy)
        self.copy_action.setToolTip("Copy annotated image to clipboard (Ctrl+C)")
        self.copy_action.triggered.connect(self.copy_to_clipboard)
        bar.addAction(self.copy_action)

        bar.addSeparator()

        # Color swatches
        self._color_buttons = []
        for name, color in PALETTE:
            btn = QToolButton(self)
            btn.setToolTip(name)
            btn.setAutoRaise(True)
            btn.setCheckable(True)
            btn.setIcon(make_color_icon(color))
            btn.clicked.connect(lambda checked, c=color: self.set_color(c))
            bar.addWidget(btn)
            self._color_buttons.append((btn, color))
        self._color_buttons[0][0].setChecked(True)

        bar.addSeparator()

        # Stroke sizes
        self._size_buttons = {}
        for size_name in STROKE_SIZES:
            btn = QToolButton(self)
            btn.setText(size_name[0])
            btn.setToolTip(f"{size_name} stroke")
            btn.setAutoRaise(True)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, n=size_name: self.set_size(n))
            bar.addWidget(btn)
            self._size_buttons[size_name] = btn
        self._size_buttons[DEFAULT_STROKE].setChecked(True)

        bar.addSeparator()

        self.outline_action = QAction(make_icon("outline", self._icon_color),
                                      "White outline / shadow", self)
        self.outline_action.setCheckable(True)
        self.outline_action.setChecked(True)
        self.outline_action.setToolTip("Toggle white outline + shadow for visibility")
        self.outline_action.triggered.connect(self.set_outline)
        bar.addAction(self.outline_action)

        bar.addSeparator()

        self.undo_action = self.canvas.undo_stack.createUndoAction(self, "Undo")
        self.undo_action.setShortcut(QKeySequence.Undo)
        self.redo_action = self.canvas.undo_stack.createRedoAction(self, "Redo")
        self.redo_action.setShortcuts(
            [QKeySequence("Ctrl+Shift+Z"), QKeySequence("Ctrl+Y")])
        bar.addAction(self.undo_action)
        bar.addAction(self.redo_action)

    def _build_menus(self):
        file_menu = self.menuBar().addMenu("&File")
        file_menu.addAction(self.open_action)
        file_menu.addSeparator()
        file_menu.addAction(self.save_action)
        file_menu.addAction(self.save_as_action)
        file_menu.addAction(self.copy_action)
        file_menu.addSeparator()
        quit_action = QAction("Quit", self)
        quit_action.setShortcut(QKeySequence.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        edit_menu = self.menuBar().addMenu("&Edit")
        edit_menu.addAction(self.undo_action)
        edit_menu.addAction(self.redo_action)
        edit_menu.addSeparator()
        delete_action = QAction("Delete selected", self)
        delete_action.triggered.connect(self.canvas.delete_selected)
        edit_menu.addAction(delete_action)

        view_menu = self.menuBar().addMenu("&View")
        for label, key, fn in [
            ("Zoom in", "Ctrl++", lambda: self.canvas.zoom_by(1.2)),
            ("Zoom out", "Ctrl+-", lambda: self.canvas.zoom_by(1 / 1.2)),
            ("Fit to window", "Ctrl+0", self.canvas.fit_to_window),
            ("Actual size", "Ctrl+1", self.canvas.actual_size),
        ]:
            action = QAction(label, self)
            action.setShortcut(key)
            action.triggered.connect(fn)
            view_menu.addAction(action)

    # ------------------------------------------------------------------ style

    def set_color(self, color):
        self.canvas.current_color = color
        for btn, c in self._color_buttons:
            btn.setChecked(c == color)
        self.canvas.apply_style_to_selection(color=color)

    def set_size(self, size_name):
        self.canvas.current_size_name = size_name
        for name, btn in self._size_buttons.items():
            btn.setChecked(name == size_name)
        self.canvas.apply_style_to_selection(
            stroke_width=STROKE_SIZES[size_name], size_name=size_name)

    def set_outline(self, enabled):
        self.canvas.current_outline = enabled
        self.canvas.apply_style_to_selection(outline=enabled)

    def _sync_tool_buttons(self, tool):
        action = self._tool_actions.get(tool)
        if action is not None and not action.isChecked():
            action.setChecked(True)

    # ------------------------------------------------------------- open/save

    def open_dialog(self):
        if not self._confirm_discard():
            return
        start_dir = os.path.dirname(self.source_path) if self.source_path else ""
        path, _ = QFileDialog.getOpenFileName(self, "Open image", start_dir, IMAGE_FILTER)
        if path:
            self.load_file(path, confirm=False)

    def load_file(self, path, confirm=True):
        if confirm and not self._confirm_discard():
            return False
        reader = QImageReader(path)
        reader.setAutoTransform(True)  # respect EXIF rotation
        image = reader.read()
        if image.isNull():
            QMessageBox.warning(self, "SkitchG",
                                f"Could not open image:\n{path}\n\n{reader.errorString()}")
            return False
        self.canvas.load_image(image.convertToFormat(QImage.Format_ARGB32_Premultiplied))
        self.source_path = path
        self.save_path = None
        self.canvas.undo_stack.setClean()
        self.canvas.set_tool("arrow")
        self._update_title()
        self.statusBar().showMessage(
            "Arrow tool active — click and drag on the image.", 6000)
        return True

    def _default_save_path(self):
        if not self.source_path:
            return os.path.expanduser("~/annotated.png")
        stem, _ext = os.path.splitext(self.source_path)
        return f"{stem}_annotated.png"

    def save(self):
        if not self.canvas.has_image():
            return
        if self.save_path:
            self._write_image(self.save_path)
        else:
            self.save_as()

    def save_as(self):
        if not self.canvas.has_image():
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save annotated image", self.save_path or self._default_save_path(),
            "PNG (*.png);;JPEG (*.jpg *.jpeg)")
        if not path:
            return
        if not os.path.splitext(path)[1]:
            path += ".png"
        if self.source_path and os.path.abspath(path) == os.path.abspath(self.source_path):
            answer = QMessageBox.question(
                self, "Overwrite original?",
                "This will overwrite the original image file.\n"
                "The unannotated original cannot be recovered. Continue?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if answer != QMessageBox.Yes:
                return
        self._write_image(path)

    def _write_image(self, path):
        image = render_annotated(self.canvas)
        if image is None:
            return
        ext = os.path.splitext(path)[1].lower()
        if ext in (".jpg", ".jpeg"):
            ok = image.save(path, "JPEG", 95)
        else:
            ok = image.save(path, "PNG")
        if ok:
            self.save_path = path
            self.canvas.undo_stack.setClean()
            self._update_title()
            self.statusBar().showMessage(f"Saved {path}", 5000)
        else:
            QMessageBox.warning(self, "SkitchG", f"Could not save to:\n{path}")

    def copy_to_clipboard(self):
        image = render_annotated(self.canvas)
        if image is None:
            return
        QGuiApplication.clipboard().setImage(image)
        self.statusBar().showMessage("Annotated image copied to clipboard.", 4000)

    # ----------------------------------------------------------------- misc

    def _update_title(self):
        name = os.path.basename(self.source_path) if self.source_path else "No image"
        dirty = "" if self.canvas.undo_stack.isClean() else " •"
        self.setWindowTitle(f"{name}{dirty} — SkitchG")

    def _confirm_discard(self):
        if not self.canvas.has_image() or self.canvas.undo_stack.isClean():
            return True
        answer = QMessageBox.question(
            self, "Unsaved annotations",
            "You have unsaved annotations. Discard them?",
            QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Cancel)
        return answer == QMessageBox.Discard

    def closeEvent(self, event):
        if self._confirm_discard():
            event.accept()
        else:
            event.ignore()

    # ------------------------------------------------------------- drag&drop

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            if url.isLocalFile():
                if self.load_file(url.toLocalFile()):
                    break
        event.acceptProposedAction()
