"""Annotation items: arrow, line, rectangle, ellipse, pen, text, pixelate.

All items are vector objects while editing and only get rasterized at export.
Scene coordinates are identical to image pixel coordinates (the background
pixmap sits at scene origin), so stroke widths are in image pixels.
"""

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QPainterPath,
    QPainterPathStroker,
    QPen,
)
from PySide6.QtWidgets import QGraphicsItem

from .palette import OUTLINE_COLOR, SHADOW_COLOR


HANDLE_SIZE = 10.0  # screen pixels (handles ignore zoom)


class HandleItem(QGraphicsItem):
    """A small draggable square used to reshape an annotation."""

    def __init__(self, parent, role):
        super().__init__(parent)
        self.role = role
        self.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
        self.setAcceptedMouseButtons(Qt.LeftButton)
        self.setCursor(Qt.SizeAllCursor)
        self.setZValue(1000)
        self._dragging = False

    def boundingRect(self):
        h = HANDLE_SIZE / 2 + 2
        return QRectF(-h, -h, 2 * h, 2 * h)

    def paint(self, painter, option, widget=None):
        h = HANDLE_SIZE / 2
        painter.setPen(QPen(QColor("#1A1A1A"), 1))
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawRect(QRectF(-h, -h, HANDLE_SIZE, HANDLE_SIZE))

    def mousePressEvent(self, event):
        self._dragging = True
        self.parentItem().begin_handle_drag()
        event.accept()

    def mouseMoveEvent(self, event):
        if self._dragging:
            scene_pos = event.scenePos()
            self.parentItem().handle_moved(self.role, scene_pos)

    def mouseReleaseEvent(self, event):
        if self._dragging:
            self._dragging = False
            self.parentItem().end_handle_drag()
        event.accept()


class AnnotationItem(QGraphicsItem):
    """Base class for all annotations: color, stroke width, outline, handles."""

    def __init__(self, color, stroke_width, outline=True):
        super().__init__()
        self.color = QColor(color)
        self.stroke_width = float(stroke_width)
        self.outline = bool(outline)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self._handles = []
        self._drag_start_state = None

    # ---- style ----

    def set_style(self, color=None, stroke_width=None, outline=None,
                  point_size=None, radius=None):
        if color is not None:
            self.color = QColor(color)
        if stroke_width is not None:
            self.stroke_width = float(stroke_width)
        if outline is not None:
            self.outline = bool(outline)
        self.prepareGeometryChange()
        self.update()

    def get_style(self):
        return {
            "color": QColor(self.color),
            "stroke_width": self.stroke_width,
            "outline": self.outline,
        }

    # ---- geometry state (for undo) ----

    def get_state(self):
        state = self._geometry_state()
        state["pos"] = QPointF(self.pos())
        return state

    def set_state(self, state):
        self.prepareGeometryChange()
        self.setPos(state["pos"])
        self._apply_geometry_state(state)
        self._layout_handles()
        self.update()

    def _geometry_state(self):
        return {}

    def _apply_geometry_state(self, state):
        pass

    # ---- handles ----

    def handle_roles(self):
        return []

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemSelectedHasChanged:
            self._set_handles_visible(bool(value))
        return super().itemChange(change, value)

    def _ensure_handles(self):
        if not self._handles:
            for role in self.handle_roles():
                self._handles.append(HandleItem(self, role))
            self._layout_handles()

    def _set_handles_visible(self, visible):
        if visible:
            self._ensure_handles()
        for h in self._handles:
            h.setVisible(visible)
        if visible:
            self._layout_handles()

    def _layout_handles(self):
        for h in self._handles:
            h.setPos(self.handle_pos(h.role))

    def handle_pos(self, role):
        return QPointF()

    def begin_handle_drag(self):
        self._drag_start_state = self.get_state()

    def handle_moved(self, role, scene_pos):
        pass

    def end_handle_drag(self):
        scene = self.scene()
        if self._drag_start_state is not None and scene is not None:
            canvas = getattr(scene, "canvas", None)
            if canvas is not None:
                canvas.geometry_edited(self, self._drag_start_state, self.get_state())
        self._drag_start_state = None

    # ---- painting helpers ----

    def _outline_width(self):
        return max(3.0, self.stroke_width * 0.45)

    def paint_selection(self, painter):
        if self.isSelected():
            pen = QPen(QColor(30, 144, 255, 200), 0, Qt.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(self.boundingRect())


class ArrowItem(AnnotationItem):
    """The Skitch-style arrow: thick tapered shaft, big filled head."""

    def __init__(self, start, end, color, stroke_width, outline=True):
        super().__init__(color, stroke_width, outline)
        self.start = QPointF(start)
        self.end = QPointF(end)

    def set_points(self, start, end):
        self.prepareGeometryChange()
        self.start = QPointF(start)
        self.end = QPointF(end)
        self._layout_handles()
        self.update()

    def _geometry_state(self):
        return {"start": QPointF(self.start), "end": QPointF(self.end)}

    def _apply_geometry_state(self, state):
        self.start = QPointF(state["start"])
        self.end = QPointF(state["end"])

    def handle_roles(self):
        return ["start", "end"]

    def handle_pos(self, role):
        return self.start if role == "start" else self.end

    def handle_moved(self, role, scene_pos):
        p = self.mapFromScene(scene_pos)
        if role == "start":
            self.set_points(p, self.end)
        else:
            self.set_points(self.start, p)

    def arrow_path(self):
        """Build the filled arrow polygon."""
        s, e = self.start, self.end
        dx, dy = e.x() - s.x(), e.y() - s.y()
        length = math.hypot(dx, dy)
        path = QPainterPath()
        if length < 1e-3:
            return path
        ux, uy = dx / length, dy / length
        px, py = -uy, ux  # perpendicular

        # Skitch proportions: the tail starts almost at a point and the
        # shaft widens continuously toward a compact triangular head.
        w = self.stroke_width
        head_len = min(max(w * 3.8, 14.0), length * 0.5)
        head_half = w * 1.35
        tail_half = max(w * 0.10, 0.8)
        neck_half = max(w * 0.72, 2.0)

        bx, by = e.x() - ux * head_len, e.y() - uy * head_len  # head base

        pts = [
            QPointF(s.x() + px * tail_half, s.y() + py * tail_half),
            QPointF(bx + px * neck_half, by + py * neck_half),
            QPointF(bx + px * head_half, by + py * head_half),
            QPointF(e.x(), e.y()),
            QPointF(bx - px * head_half, by - py * head_half),
            QPointF(bx - px * neck_half, by - py * neck_half),
            QPointF(s.x() - px * tail_half, s.y() - py * tail_half),
        ]
        path.moveTo(pts[0])
        for p in pts[1:]:
            path.lineTo(p)
        path.closeSubpath()
        return path

    def boundingRect(self):
        m = self._outline_width() + self.stroke_width * 2 + 6
        return QRectF(self.start, self.end).normalized().adjusted(-m, -m, m, m)

    def shape(self):
        stroker = QPainterPathStroker()
        stroker.setWidth(max(self.stroke_width * 2, 12.0))
        base = self.arrow_path()
        return stroker.createStroke(base).united(base)

    def paint(self, painter, option, widget=None):
        path = self.arrow_path()
        if path.isEmpty():
            return
        painter.setRenderHint(painter.RenderHint.Antialiasing, True)
        if self.outline:
            painter.setPen(Qt.NoPen)
            painter.setBrush(SHADOW_COLOR)
            painter.drawPath(path.translated(1.5, 2.0))
            painter.setPen(QPen(OUTLINE_COLOR, self._outline_width() * 2,
                                Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.setBrush(OUTLINE_COLOR)
            painter.drawPath(path)
        # Rounded joins on the fill itself: stroke with same color.
        painter.setPen(QPen(self.color, max(1.5, self.stroke_width * 0.35),
                            Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.setBrush(self.color)
        painter.drawPath(path)
        self.paint_selection(painter)


class LineItem(AnnotationItem):
    """A straight thick line with rounded caps."""

    def __init__(self, start, end, color, stroke_width, outline=True):
        super().__init__(color, stroke_width, outline)
        self.start = QPointF(start)
        self.end = QPointF(end)

    set_points = ArrowItem.set_points
    _geometry_state = ArrowItem._geometry_state
    _apply_geometry_state = ArrowItem._apply_geometry_state
    handle_roles = ArrowItem.handle_roles
    handle_pos = ArrowItem.handle_pos
    handle_moved = ArrowItem.handle_moved

    def line_path(self):
        path = QPainterPath(self.start)
        path.lineTo(self.end)
        return path

    def boundingRect(self):
        m = self._outline_width() + self.stroke_width + 6
        return QRectF(self.start, self.end).normalized().adjusted(-m, -m, m, m)

    def shape(self):
        stroker = QPainterPathStroker()
        stroker.setWidth(max(self.stroke_width * 2, 12.0))
        stroker.setCapStyle(Qt.RoundCap)
        return stroker.createStroke(self.line_path())

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(painter.RenderHint.Antialiasing, True)
        path = self.line_path()
        if self.outline:
            painter.setPen(QPen(SHADOW_COLOR, self.stroke_width + 2 * self._outline_width(),
                                Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.drawPath(path.translated(1.5, 2.0))
            painter.setPen(QPen(OUTLINE_COLOR, self.stroke_width + 2 * self._outline_width(),
                                Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.drawPath(path)
        painter.setPen(QPen(self.color, self.stroke_width,
                            Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawPath(path)
        self.paint_selection(painter)


class _RectBasedItem(AnnotationItem):
    """Shared logic for rectangle-shaped annotations with corner handles."""

    def __init__(self, rect, color, stroke_width, outline=True):
        super().__init__(color, stroke_width, outline)
        self.rect = QRectF(rect).normalized()

    def set_rect(self, rect):
        self.prepareGeometryChange()
        self.rect = QRectF(rect).normalized()
        self._layout_handles()
        self.update()

    def _geometry_state(self):
        return {"rect": QRectF(self.rect)}

    def _apply_geometry_state(self, state):
        self.rect = QRectF(state["rect"])

    def handle_roles(self):
        return ["tl", "tr", "bl", "br"]

    def handle_pos(self, role):
        r = self.rect
        return {"tl": r.topLeft(), "tr": r.topRight(),
                "bl": r.bottomLeft(), "br": r.bottomRight()}[role]

    def handle_moved(self, role, scene_pos):
        p = self.mapFromScene(scene_pos)
        r = QRectF(self.rect)
        if role == "tl":
            r.setTopLeft(p)
        elif role == "tr":
            r.setTopRight(p)
        elif role == "bl":
            r.setBottomLeft(p)
        else:
            r.setBottomRight(p)
        self.set_rect(r)

    def boundingRect(self):
        m = self._outline_width() + self.stroke_width + 6
        return self.rect.adjusted(-m, -m, m, m)

    def shape(self):
        path = QPainterPath()
        path.addRect(self.rect)
        stroker = QPainterPathStroker()
        stroker.setWidth(max(self.stroke_width * 2, 12.0))
        return stroker.createStroke(path)

    def _shape_path(self):
        raise NotImplementedError

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(painter.RenderHint.Antialiasing, True)
        path = self._shape_path()
        painter.setBrush(Qt.NoBrush)
        if self.outline:
            painter.setPen(QPen(SHADOW_COLOR, self.stroke_width + 2 * self._outline_width(),
                                Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.drawPath(path.translated(1.5, 2.0))
            painter.setPen(QPen(OUTLINE_COLOR, self.stroke_width + 2 * self._outline_width(),
                                Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.drawPath(path)
        painter.setPen(QPen(self.color, self.stroke_width,
                            Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawPath(path)
        self.paint_selection(painter)


class RectItem(_RectBasedItem):
    def _shape_path(self):
        path = QPainterPath()
        path.addRect(self.rect)  # Skitch rectangles have sharp corners
        return path


class EllipseItem(_RectBasedItem):
    def _shape_path(self):
        path = QPainterPath()
        path.addEllipse(self.rect)
        return path

    def shape(self):
        path = self._shape_path()
        stroker = QPainterPathStroker()
        stroker.setWidth(max(self.stroke_width * 2, 12.0))
        return stroker.createStroke(path)


class PenItem(AnnotationItem):
    """Freehand stroke."""

    def __init__(self, points, color, stroke_width, outline=True):
        super().__init__(color, stroke_width, outline)
        self.points = [QPointF(p) for p in points]

    def add_point(self, p):
        self.prepareGeometryChange()
        self.points.append(QPointF(p))
        self.update()

    def _geometry_state(self):
        return {"points": [QPointF(p) for p in self.points]}

    def _apply_geometry_state(self, state):
        self.points = [QPointF(p) for p in state["points"]]

    def pen_path(self):
        path = QPainterPath()
        if not self.points:
            return path
        path.moveTo(self.points[0])
        if len(self.points) == 1:
            path.lineTo(self.points[0] + QPointF(0.01, 0))
        for p in self.points[1:]:
            path.lineTo(p)
        return path

    def boundingRect(self):
        if not self.points:
            return QRectF()
        m = self._outline_width() + self.stroke_width + 6
        return self.pen_path().boundingRect().adjusted(-m, -m, m, m)

    def shape(self):
        stroker = QPainterPathStroker()
        stroker.setWidth(max(self.stroke_width * 2, 12.0))
        stroker.setCapStyle(Qt.RoundCap)
        return stroker.createStroke(self.pen_path())

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(painter.RenderHint.Antialiasing, True)
        path = self.pen_path()
        if self.outline:
            painter.setPen(QPen(OUTLINE_COLOR, self.stroke_width + 2 * self._outline_width(),
                                Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.drawPath(path)
        painter.setPen(QPen(self.color, self.stroke_width,
                            Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawPath(path)
        self.paint_selection(painter)


class TextItem(AnnotationItem):
    """Bold annotation text with a white outline for readability.

    Editing is a simple append/backspace model driven by the canvas:
    click to place, type, Enter commits, Escape cancels.
    """

    def __init__(self, pos, color, point_size, outline=True):
        super().__init__(color, point_size, outline)
        self.setPos(pos)
        self.text = ""
        self.point_size = float(point_size)
        self.editing = False

    def font(self):
        font = QFont("Sans Serif")
        font.setPointSizeF(self.point_size)
        font.setBold(True)
        return font

    def set_text(self, text):
        self.prepareGeometryChange()
        self.text = text
        self.update()

    def set_style(self, color=None, stroke_width=None, outline=None,
                  point_size=None, radius=None):
        # The size choice maps to a text point size instead of stroke width.
        if point_size is not None:
            self.prepareGeometryChange()
            self.point_size = float(point_size)
        super().set_style(color=color, outline=outline)

    def get_style(self):
        return {
            "color": QColor(self.color),
            "outline": self.outline,
            "point_size": self.point_size,
        }

    def _geometry_state(self):
        return {"text": self.text, "point_size": self.point_size}

    def _apply_geometry_state(self, state):
        self.text = state["text"]
        self.point_size = state["point_size"]

    def _display_text(self):
        return self.text + ("‸" if self.editing else "")

    def _lines(self):
        return self._display_text().split("\n") or [""]

    def text_path(self):
        path = QPainterPath()
        font = self.font()
        metrics = QFontMetricsF(font)
        y = metrics.ascent()
        for line in self._lines():
            if line:
                path.addText(0, y, font, line)
            y += metrics.lineSpacing()
        return path

    def boundingRect(self):
        metrics = QFontMetricsF(self.font())
        width = max([metrics.horizontalAdvance(l) for l in self._lines()] + [10.0])
        height = metrics.lineSpacing() * len(self._lines())
        m = self._outline_width() + 8
        return QRectF(0, 0, width, height).adjusted(-m, -m, m, m)

    def shape(self):
        path = QPainterPath()
        path.addRect(self.boundingRect())
        return path

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(painter.RenderHint.Antialiasing, True)
        path = self.text_path()
        outline_w = max(2.5, self.point_size / 7.0)
        # Skitch text always carries the white outline for readability.
        painter.setPen(Qt.NoPen)
        painter.setBrush(SHADOW_COLOR)
        painter.drawPath(path.translated(1.5, 2.0))
        painter.strokePath(path, QPen(OUTLINE_COLOR, outline_w * 2,
                                      Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.fillPath(path, self.color)
        if self.editing:
            pen = QPen(QColor(30, 144, 255, 220), 0, Qt.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(self.boundingRect())
        else:
            self.paint_selection(painter)

    def _outline_width(self):
        return max(2.5, self.point_size / 7.0)


class MarkerItem(AnnotationItem):
    """Skitch-style numbered marker: a round pin head with a pointer tail.

    The tail tip sits on the thing you're pointing at; the head holds an
    auto-incremented number (editable, double-click). Drag while placing
    to aim the tail in any direction.
    """

    MAX_CHARS = 3

    def __init__(self, tip, color, radius, text="1", outline=True):
        super().__init__(color, radius, outline)
        self.tip = QPointF(tip)
        self.radius = float(radius)
        self.head = QPointF(tip.x(), tip.y() - self.default_offset())
        self.text = text
        self.editing = False

    def default_offset(self):
        return self.radius * 1.9

    def set_geometry(self, tip=None, head=None):
        self.prepareGeometryChange()
        if tip is not None:
            self.tip = QPointF(tip)
        if head is not None:
            head = QPointF(head)
            # Skitch pins are compact: dragging mostly aims the stubby tail,
            # so the head stays within a narrow distance band from the tip.
            v = head - self.tip
            dist = math.hypot(v.x(), v.y())
            if dist < 1e-3:
                v, dist = QPointF(0, -1), 1.0
            clamped = max(self.radius * 1.6, min(self.radius * 2.3, dist))
            self.head = self.tip + v * (clamped / dist)
        self._layout_handles()
        self.update()

    def set_text(self, text):
        self.prepareGeometryChange()
        self.text = text[: self.MAX_CHARS]
        self.update()

    def _geometry_state(self):
        return {"tip": QPointF(self.tip), "head": QPointF(self.head),
                "text": self.text, "radius": self.radius}

    def _apply_geometry_state(self, state):
        self.tip = QPointF(state["tip"])
        self.head = QPointF(state["head"])
        self.text = state["text"]
        self.radius = state["radius"]

    def set_style(self, color=None, stroke_width=None, outline=None,
                  point_size=None, radius=None):
        if radius is not None:
            self.prepareGeometryChange()
            self.radius = float(radius)
        AnnotationItem.set_style(self, color=color, outline=outline)

    def get_style(self):
        return {
            "color": QColor(self.color),
            "outline": self.outline,
            "radius": self.radius,
        }

    def handle_roles(self):
        return ["tip", "head"]

    def handle_pos(self, role):
        return self.tip if role == "tip" else self.head

    def handle_moved(self, role, scene_pos):
        p = self.mapFromScene(scene_pos)
        if role == "tip":
            self.set_geometry(tip=p)
        else:
            self.set_geometry(head=p)

    def marker_path(self):
        """Map-pin shape: round head with a short, wide integrated pointer,
        like the classic Skitch stamps."""
        r = self.radius
        head_path = QPainterPath()
        head_path.addEllipse(self.head, r, r)

        v = self.tip - self.head
        dist = math.hypot(v.x(), v.y())
        if dist < 1e-3:
            return head_path
        ux, uy = v.x() / dist, v.y() / dist
        px, py = -uy, ux
        base_half = r * 0.74
        # Anchor the pointer base slightly toward the tip so it merges
        # smoothly with the circle instead of crossing its center.
        base = self.head + QPointF(ux * r * 0.35, uy * r * 0.35)
        tail = QPainterPath()
        tail.moveTo(base + QPointF(px * base_half, py * base_half))
        tail.lineTo(self.tip)
        tail.lineTo(base - QPointF(px * base_half, py * base_half))
        tail.closeSubpath()
        return head_path.united(tail)

    def _text_color(self):
        # Dark digits on light marker colors (white, yellow), white otherwise.
        c = self.color
        luminance = 0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()
        return QColor("#1A1A1A") if luminance > 180 else QColor("#FFFFFF")

    def _outline_width(self):
        return max(2.5, self.radius * 0.16)

    def boundingRect(self):
        m = self._outline_width() * 2 + 6
        rect = QRectF(self.head.x() - self.radius, self.head.y() - self.radius,
                      2 * self.radius, 2 * self.radius)
        return rect.united(QRectF(self.tip, self.tip)).adjusted(-m, -m, m, m)

    def shape(self):
        return self.marker_path()

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(painter.RenderHint.Antialiasing, True)
        path = self.marker_path()
        # Skitch pins always carry the white outline + shadow.
        painter.setPen(Qt.NoPen)
        painter.setBrush(SHADOW_COLOR)
        painter.drawPath(path.translated(1.5, 2.0))
        painter.setPen(QPen(OUTLINE_COLOR, self._outline_width() * 2,
                            Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.setBrush(OUTLINE_COLOR)
        painter.drawPath(path)
        painter.setPen(Qt.NoPen)
        painter.setBrush(self.color)
        painter.drawPath(path)

        # The number, centered in the head, shrunk to fit longer labels.
        display = self.text + ("‸" if self.editing else "")
        font = QFont("Sans Serif")
        font.setBold(True)
        font.setPixelSize(max(8, int(self.radius * (1.15 if len(display) <= 1 else
                                                    0.95 if len(display) == 2 else 0.72))))
        painter.setFont(font)
        painter.setPen(self._text_color())
        head_rect = QRectF(self.head.x() - self.radius, self.head.y() - self.radius,
                           2 * self.radius, 2 * self.radius)
        painter.drawText(head_rect, Qt.AlignCenter, display)

        if self.editing:
            painter.setPen(QPen(QColor(30, 144, 255, 220), 0, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(self.boundingRect())
        else:
            self.paint_selection(painter)


class PixelateItem(_RectBasedItem):
    """Pixelates the underlying base image region (for sensitive info)."""

    BLOCK = 12  # pixel block size in image coordinates

    def __init__(self, rect, get_base_image, color, stroke_width):
        super().__init__(rect, color, stroke_width, outline=False)
        self._get_base_image = get_base_image

    def boundingRect(self):
        return self.rect.adjusted(-2, -2, 2, 2)

    def shape(self):
        path = QPainterPath()
        path.addRect(self.rect)
        return path

    def paint(self, painter, option, widget=None):
        image = self._get_base_image()
        if image is None or self.rect.isEmpty():
            return
        # Item may have been moved: map our rect to scene == image coords.
        scene_rect = self.mapRectToScene(self.rect)
        src = scene_rect.toAlignedRect().intersected(image.rect())
        if src.isEmpty():
            return
        region = image.copy(src)
        small_w = max(1, src.width() // self.BLOCK)
        small_h = max(1, src.height() // self.BLOCK)
        pixelated = region.scaled(small_w, small_h).scaled(
            src.width(), src.height(),
            Qt.IgnoreAspectRatio, Qt.FastTransformation)
        painter.setRenderHint(painter.RenderHint.SmoothPixmapTransform, False)
        target = self.mapRectFromScene(QRectF(src))
        painter.drawImage(target, pixelated)
        self.paint_selection(painter)
