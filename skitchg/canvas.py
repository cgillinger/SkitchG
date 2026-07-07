"""The annotation canvas: a QGraphicsView with the image and tool handling."""

import math

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap, QUndoStack
from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsScene, QGraphicsView

from .commands import (
    AddItemCommand,
    CropCommand,
    GeometryCommand,
    MoveItemsCommand,
    RemoveItemsCommand,
    StyleCommand,
)
from .items import (
    AnnotationItem,
    ArrowItem,
    EllipseItem,
    HandleItem,
    LineItem,
    MarkerItem,
    PenItem,
    PixelateItem,
    RectItem,
    TextItem,
)
from .palette import (
    CANVAS_BG,
    DEFAULT_COLOR,
    DEFAULT_STROKE,
    MARKER_RADII,
    STROKE_SIZES,
    TEXT_SIZES,
)

MIN_DRAG = 6.0  # px before a drag counts as a shape


class Canvas(QGraphicsView):
    dirty_changed = Signal()
    tool_changed = Signal(str)
    size_adjusted = Signal()  # wheel changed the size away from the preset

    def __init__(self, parent=None):
        super().__init__(parent)
        scene = QGraphicsScene(self)
        scene.canvas = self
        self.setScene(scene)
        self.setBackgroundBrush(CANVAS_BG)
        self.setRenderHint(QPainter.Antialiasing, True)
        self.setRenderHint(QPainter.SmoothPixmapTransform, True)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.NoDrag)
        # Repaint the whole viewport on every change. Partial updates left
        # ghost residue from cosmetic pens (selection rect, zoom-independent
        # handles) that straddle the dirty region by a device pixel when the
        # view is zoomed out — cheap insurance for one image + a few vectors.
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setAcceptDrops(False)  # main window handles drops

        self.undo_stack = QUndoStack(self)

        self._pixmap_item = None
        self._image = None

        self.tool = "arrow"
        self.current_color = QColor(DEFAULT_COLOR)
        self.current_size_name = DEFAULT_STROKE
        # Skitch draws arrows/shapes flat; text and pins are always outlined.
        self.current_outline = False
        # Sizes are in image pixels, so they scale with the image resolution
        # (a 4px arrow is invisible on a 24MP photo). The multiplier is the
        # on-the-fly adjustment driven by the mouse wheel.
        self.image_scale = 1.0
        self.size_multiplier = 1.0

        self._temp_item = None       # item being drawn right now
        self._drag_start = None
        self._crop_overlay = None
        self._editing_text = None    # TextItem in edit mode
        self._edit_old_state = None  # state before re-editing existing text
        self._move_snapshot = []     # (item, pos) at mouse press in select mode
        self._handle_drag = False    # a reshape handle grabbed the mouse
        self._auto_fit = True        # refit on resize until the user zooms manually

    # ------------------------------------------------------------------ image

    def load_image(self, image):
        """Set a new base image, clearing all annotations."""
        self.scene().clear()
        self._pixmap_item = QGraphicsPixmapItem(QPixmap.fromImage(image))
        self._pixmap_item.setZValue(-10)
        self.scene().addItem(self._pixmap_item)
        self._image = image
        self.scene().setSceneRect(QRectF(image.rect()))
        self.image_scale = max(1.0, math.hypot(image.width(), image.height()) / 1200.0)
        self.size_multiplier = 1.0
        self.undo_stack.clear()
        self._temp_item = None
        self._editing_text = None
        self.fit_to_window()

    def set_base_image(self, image):
        """Swap the base image in place (used by crop undo/redo)."""
        self._image = image
        self._pixmap_item.setPixmap(QPixmap.fromImage(image))
        self.scene().setSceneRect(QRectF(image.rect()))
        self.fit_to_window()

    def base_image(self):
        return self._image

    def has_image(self):
        return self._image is not None

    def annotation_items(self):
        return [i for i in self.scene().items() if isinstance(i, AnnotationItem)]

    def mark_dirty(self):
        self.dirty_changed.emit()

    # ------------------------------------------------------------------ tools

    def set_tool(self, tool):
        self.commit_text_edit()
        self.cancel_current(deselect=False)
        self.tool = tool
        self.setDragMode(
            QGraphicsView.RubberBandDrag if tool == "select" else QGraphicsView.NoDrag)
        if tool == "select":
            self.setCursor(Qt.ArrowCursor)
        elif tool == "text":
            self.setCursor(Qt.IBeamCursor)
        else:
            self.setCursor(Qt.CrossCursor)
        self.tool_changed.emit(tool)

    def stroke_width(self):
        return STROKE_SIZES[self.current_size_name] * self.image_scale * self.size_multiplier

    def text_point_size(self):
        return TEXT_SIZES[self.current_size_name] * self.image_scale * self.size_multiplier

    def marker_radius(self):
        return MARKER_RADII[self.current_size_name] * self.image_scale * self.size_multiplier

    def effective_style(self):
        """The three size values, scaled to the current image and multiplier."""
        return {
            "stroke_width": self.stroke_width(),
            "point_size": self.text_point_size(),
            "radius": self.marker_radius(),
        }

    def apply_style_to_selection(self, **style):
        items = [i for i in self.scene().selectedItems() if isinstance(i, AnnotationItem)]
        if items:
            self.undo_stack.push(StyleCommand(self, [(i, style) for i in items]))

    def adjust_size(self, direction):
        """Skitch-style on-the-fly resize (mouse wheel): scales the pending
        style, the item being drawn/edited, and any selected annotations —
        each relative to its own current size."""
        factor = 1.12 if direction > 0 else 1 / 1.12
        # Tight clamp: a runaway multiplier made every new shape enormous
        # while the S/M/L buttons still looked active.
        new_multiplier = max(0.5, min(2.5, self.size_multiplier * factor))
        if new_multiplier == self.size_multiplier:
            return
        self.size_multiplier = new_multiplier
        self.size_adjusted.emit()

        for item in (self._temp_item, self._editing_text):
            if item is not None:
                item.set_style(**self._scaled_sizes(item, factor))
        pairs = [(i, self._scaled_sizes(i, factor))
                 for i in self.scene().selectedItems()
                 if isinstance(i, AnnotationItem)]
        if pairs:
            self.undo_stack.push(StyleCommand(self, pairs, mergeable=True))

        window = self.window()
        if hasattr(window, "statusBar"):
            window.statusBar().showMessage(
                f"Size: {self.stroke_width():.0f} px stroke — scroll to adjust, "
                f"XS/S/M/L to reset", 2500)

    @staticmethod
    def _scaled_sizes(item, factor):
        return {key: value * factor for key, value in item.get_style().items()
                if key in ("stroke_width", "point_size", "radius")}

    # ------------------------------------------------------------- mouse/keys

    def mousePressEvent(self, event):
        if not self.has_image() or event.button() != Qt.LeftButton:
            super().mousePressEvent(event)
            return

        pos = self.mapToScene(event.position().toPoint())

        if self._editing_text is not None:
            # Clicking outside the text being edited commits it.
            if self._editing_text not in self.items(event.position().toPoint()):
                self.commit_text_edit()
            else:
                return

        # Reshape handles on a selected annotation always win over drawing a
        # new item, no matter which tool is active.
        if any(isinstance(i, HandleItem) and i.isVisible()
               for i in self.items(event.position().toPoint())):
            self._handle_drag = True
            super().mousePressEvent(event)
            return

        if self.tool == "select":
            self._move_snapshot = [(i, QPointF(i.pos())) for i in self.annotation_items()]
            super().mousePressEvent(event)
            return

        if self.tool == "text":
            item = self._editable_item_at(event.position().toPoint())
            if item is not None:
                self.start_text_edit(item)
            else:
                self._create_text(pos)
            return

        if self.tool == "marker":
            existing = self._editable_item_at(event.position().toPoint())
            if isinstance(existing, MarkerItem):
                self.start_text_edit(existing)
                return
            self._drag_start = pos
            self._temp_item = MarkerItem(
                pos, self.current_color, self.marker_radius(),
                text=str(self._next_marker_number()), outline=self.current_outline)
            self._temp_item.setZValue(self._next_z())
            self.scene().addItem(self._temp_item)
            return

        self._drag_start = pos
        w = self.stroke_width()
        if self.tool == "arrow":
            self._temp_item = ArrowItem(pos, pos, self.current_color, w, self.current_outline)
        elif self.tool == "line":
            self._temp_item = LineItem(pos, pos, self.current_color, w, self.current_outline)
        elif self.tool == "rect":
            self._temp_item = RectItem(QRectF(pos, pos), self.current_color, w, self.current_outline)
        elif self.tool == "ellipse":
            self._temp_item = EllipseItem(QRectF(pos, pos), self.current_color, w, self.current_outline)
        elif self.tool == "pen":
            self._temp_item = PenItem([pos], self.current_color, w, self.current_outline)
        elif self.tool == "pixelate":
            self._temp_item = PixelateItem(QRectF(pos, pos), self.base_image, self.current_color, w)
        elif self.tool == "crop":
            self._crop_overlay = QGraphicsRectItem(QRectF(pos, pos))
            pen = QPen(QColor("#FFFFFF"), 0, Qt.DashLine)
            self._crop_overlay.setPen(pen)
            self._crop_overlay.setBrush(QColor(255, 255, 255, 40))
            self._crop_overlay.setZValue(2000)
            self.scene().addItem(self._crop_overlay)

        if self._temp_item is not None:
            self._temp_item.setZValue(self._next_z())
            self.scene().addItem(self._temp_item)

    def mouseMoveEvent(self, event):
        if self._drag_start is None and self._crop_overlay is None:
            super().mouseMoveEvent(event)
            return
        pos = self.mapToScene(event.position().toPoint())
        item = self._temp_item
        if isinstance(item, (ArrowItem, LineItem)):
            item.set_points(self._drag_start, pos)
        elif isinstance(item, (RectItem, EllipseItem, PixelateItem)):
            item.set_rect(QRectF(self._drag_start, pos))
        elif isinstance(item, PenItem):
            item.add_point(pos)
        elif isinstance(item, MarkerItem):
            item.set_geometry(head=pos)
        elif self._crop_overlay is not None:
            self._crop_overlay.setRect(QRectF(self._drag_start, pos).normalized())

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton:
            super().mouseReleaseEvent(event)
            return

        if self._handle_drag:
            self._handle_drag = False
            super().mouseReleaseEvent(event)
            return

        if self.tool == "select":
            super().mouseReleaseEvent(event)
            self._push_moves()
            return

        pos = self.mapToScene(event.position().toPoint())

        if self._crop_overlay is not None:
            rect = self._crop_overlay.rect()
            self.scene().removeItem(self._crop_overlay)
            self._crop_overlay = None
            self._drag_start = None
            self._apply_crop(rect)
            return

        if self._temp_item is None:
            self._drag_start = None
            return

        item = self._temp_item
        self._temp_item = None
        start = self._drag_start
        self._drag_start = None

        drag_len = (pos - start).manhattanLength() if start is not None else 0
        big_enough = (drag_len >= MIN_DRAG
                      or isinstance(item, (PenItem, MarkerItem)))
        if not big_enough:
            self.scene().removeItem(item)
            return

        self.undo_stack.push(AddItemCommand(self, item))
        # Keep the fresh annotation selected so the wheel resizes it directly.
        self.scene().clearSelection()
        item.setSelected(True)

    def mouseDoubleClickEvent(self, event):
        if self.tool == "select":
            item = self._editable_item_at(event.position().toPoint())
            if item is not None:
                self.start_text_edit(item)
                return
        super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            factor = 1.2 if event.angleDelta().y() > 0 else 1 / 1.2
            self.zoom_by(factor)
            return
        # Skitch-style on-the-fly resize: plain scroll adjusts annotation
        # size whenever a drawing tool is active or something is selected.
        has_selection = bool(self.scene() and self.scene().selectedItems())
        if self.has_image() and (self.tool not in ("select", "crop") or has_selection
                                 or self._temp_item is not None):
            self.adjust_size(event.angleDelta().y())
            return
        super().wheelEvent(event)

    TOOL_KEYS = {
        Qt.Key_V: "select",
        Qt.Key_A: "arrow",
        Qt.Key_L: "line",
        Qt.Key_R: "rect",
        Qt.Key_E: "ellipse",
        Qt.Key_P: "pen",
        Qt.Key_T: "text",
        Qt.Key_M: "marker",
        Qt.Key_X: "pixelate",
        Qt.Key_C: "crop",
    }

    def keyPressEvent(self, event):
        if self._editing_text is not None:
            self._handle_text_key(event)
            return
        if event.key() == Qt.Key_Escape:
            self.cancel_current()
            return
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            self.delete_selected()
            return
        if not event.modifiers() and event.key() in self.TOOL_KEYS:
            self.set_tool(self.TOOL_KEYS[event.key()])
            return
        super().keyPressEvent(event)

    # ------------------------------------------------------------------- text

    def _create_text(self, pos):
        item = TextItem(pos, self.current_color, self.text_point_size(), self.current_outline)
        item.setZValue(self._next_z())
        self.scene().addItem(item)
        self.start_text_edit(item, is_new=True)

    def start_text_edit(self, item, is_new=False):
        self.commit_text_edit()
        self._editing_text = item
        self._edit_old_state = None if is_new else item.get_state()
        item.editing = True
        item.update()
        self.setFocus()

    def commit_text_edit(self):
        item = self._editing_text
        if item is None:
            return
        self._editing_text = None
        item.editing = False
        item.update()
        old_state = self._edit_old_state
        self._edit_old_state = None
        if not item.text.strip():
            # Empty text: remove entirely (and undo nothing).
            if old_state is not None:
                item.set_state(old_state)
                if not item.text.strip():
                    self.scene().removeItem(item)
            else:
                self.scene().removeItem(item)
            return
        if old_state is None:
            self.undo_stack.push(AddItemCommand(self, item, "Add text"))
        elif old_state != item.get_state():
            self.undo_stack.push(
                GeometryCommand(self, item, old_state, item.get_state(), "Edit text"))
        # Keep it selected so the wheel resizes it right after typing.
        self.scene().clearSelection()
        item.setSelected(True)

    def cancel_text_edit(self):
        item = self._editing_text
        if item is None:
            return
        self._editing_text = None
        item.editing = False
        if self._edit_old_state is not None:
            item.set_state(self._edit_old_state)
            self._edit_old_state = None
        else:
            self.scene().removeItem(item)

    def _handle_text_key(self, event):
        item = self._editing_text
        key = event.key()
        if key == Qt.Key_Escape:
            self.cancel_text_edit()
        elif key in (Qt.Key_Return, Qt.Key_Enter):
            if event.modifiers() & Qt.ShiftModifier and isinstance(item, TextItem):
                item.set_text(item.text + "\n")
            else:
                self.commit_text_edit()
        elif key == Qt.Key_Backspace:
            item.set_text(item.text[:-1])
        elif event.text() and event.text().isprintable():
            item.set_text(item.text + event.text())

    def _editable_item_at(self, view_pos):
        for item in self.items(view_pos):
            if isinstance(item, (TextItem, MarkerItem)):
                return item
        return None

    def _next_marker_number(self):
        numbers = [int(i.text) for i in self.annotation_items()
                   if isinstance(i, MarkerItem) and i.text.isdigit()]
        return max(numbers, default=0) + 1

    # ------------------------------------------------------------ edit/select

    def geometry_edited(self, item, old_state, new_state):
        self.undo_stack.push(GeometryCommand(self, item, old_state, new_state))

    def _push_moves(self):
        moves = []
        snapshot = self._move_snapshot
        self._move_snapshot = []
        for item, old_pos in snapshot:
            if item.scene() is self.scene() and item.pos() != old_pos:
                moves.append((item, old_pos, QPointF(item.pos())))
        if moves:
            self.undo_stack.push(MoveItemsCommand(self, moves))

    def delete_selected(self):
        items = [i for i in self.scene().selectedItems() if isinstance(i, AnnotationItem)]
        if items:
            self.undo_stack.push(RemoveItemsCommand(self, items))

    def cancel_current(self, deselect=True):
        self.cancel_text_edit()
        if self._temp_item is not None:
            self.scene().removeItem(self._temp_item)
            self._temp_item = None
        if self._crop_overlay is not None:
            self.scene().removeItem(self._crop_overlay)
            self._crop_overlay = None
        self._drag_start = None
        if deselect:
            self.scene().clearSelection()

    def _apply_crop(self, rect):
        crop = rect.toAlignedRect().intersected(self._image.rect())
        if crop.width() < 8 or crop.height() < 8:
            return
        if crop == self._image.rect():
            return
        self.undo_stack.push(CropCommand(self, crop))

    def _next_z(self):
        items = self.annotation_items()
        return max((i.zValue() for i in items), default=0) + 1

    # ------------------------------------------------------------------- view

    def fit_to_window(self):
        if self.has_image():
            self._auto_fit = True
            self.fitInView(QRectF(self._image.rect()), Qt.KeepAspectRatio)
            # Never zoom in beyond 100% when fitting.
            if self.transform().m11() > 1.0:
                self.resetTransform()

    def actual_size(self):
        self._auto_fit = False
        self.resetTransform()

    def zoom_by(self, factor):
        self._auto_fit = False
        current = self.transform().m11()
        new = max(0.05, min(8.0, current * factor))
        self.setTransform(self.transform().scale(new / current, new / current))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._auto_fit:
            self.fit_to_window()

    def showEvent(self, event):
        super().showEvent(event)
        if self._auto_fit:
            self.fit_to_window()
