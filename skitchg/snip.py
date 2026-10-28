"""Skitch-style region picker: frozen screen, drag a rectangle, done."""

from PySide6.QtCore import QObject, QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from .fonts import sans_font

DIM = QColor(0, 0, 0, 115)  # ~45% black
MIN_DRAG = 5                # px; anything shorter counts as a click


class SnipOverlay(QWidget):
    """Fullscreen frozen copy of one screen."""

    def __init__(self, session, screen, image):
        super().__init__()
        self._session = session
        self._image = image
        self._press = None   # drag start, widget coordinates
        self._cursor = None  # current drag position
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setCursor(Qt.CrossCursor)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setScreen(screen)
        self.setGeometry(screen.geometry())

    def open(self):
        self.showFullScreen()
        self.raise_()
        self.activateWindow()
        self.setFocus()

    # --------------------------------------------------------- selection math

    def selection_rect(self):
        """Current drag as a normalized widget-space rect, or None."""
        if self._press is None or self._cursor is None:
            return None
        # Not QRect(p1, p2): that is inclusive and would be one pixel too big.
        delta = self._cursor - self._press
        return QRect(QPoint(min(self._press.x(), self._cursor.x()),
                            min(self._press.y(), self._cursor.y())),
                     QSize(abs(delta.x()), abs(delta.y())))

    def is_click(self):
        delta = self._cursor - self._press
        return abs(delta.x()) < MIN_DRAG and abs(delta.y()) < MIN_DRAG

    def to_image_rect(self, rect):
        """Map a widget-space rect to image pixels (the image is physical)."""
        scale = self._image.width() / self.width()
        mapped = QRect(round(rect.x() * scale), round(rect.y() * scale),
                       max(1, round(rect.width() * scale)),
                       max(1, round(rect.height() * scale)))
        return mapped.intersected(self._image.rect())

    def crop_selection(self):
        if self.is_click():
            return self._image.copy()
        return self._image.copy(self.to_image_rect(self.selection_rect()))

    def clear_selection(self):
        self._press = self._cursor = None
        self.update()

    # ----------------------------------------------------------------- events

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            self._session.cancel()
            return
        if event.button() != Qt.LeftButton:
            return
        self._session.begin_selection(self)
        self._press = self._cursor = event.position().toPoint()
        self.update()

    def mouseMoveEvent(self, event):
        if self._press is not None:
            self._cursor = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton or self._press is None:
            return
        self._cursor = event.position().toPoint()
        self._session.finish(self.crop_selection())

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self._session.cancel()

    def paintEvent(self, event):
        p = QPainter(self)
        p.drawImage(self.rect(), self._image)
        p.fillRect(self.rect(), DIM)
        sel = self.selection_rect()
        if sel is None or sel.isEmpty():
            return
        # Undimmed selection: redraw just that part of the frozen image.
        p.drawImage(sel, self._image, self.to_image_rect(sel))
        p.setPen(QPen(QColor("#FFFFFF"), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRect(sel)
        p.setPen(QPen(QColor("#1E8FE1"), 1, Qt.DashLine))
        p.drawRect(sel.adjusted(1, 1, -1, -1))

        size = self.to_image_rect(sel).size()
        label = f"{size.width()} × {size.height()}"
        p.setFont(sans_font(10))
        box = p.fontMetrics().boundingRect(label).adjusted(-6, -3, 6, 3)
        # Above the selection if there is room, otherwise inside its corner.
        y = sel.top() - box.height() - 4
        box.moveTo(QPoint(sel.left(), y if y >= 0 else sel.top() + 4))
        p.fillRect(box, QColor(0, 0, 0, 190))
        p.setPen(QColor("#FFFFFF"))
        p.drawText(box, Qt.AlignCenter, label)


class SnipSession(QObject):
    """One overlay per screen; emits finished(QImage or None) exactly once."""

    finished = Signal(object)

    def __init__(self, screens, parent=None):
        super().__init__(parent)
        self._overlays = [SnipOverlay(self, s, i) for s, i in screens]
        self._done = False

    def start(self):
        for overlay in self._overlays:
            overlay.open()

    def begin_selection(self, active):
        # There is only one selection: starting it on one screen clears
        # any leftover on the others.
        for overlay in self._overlays:
            if overlay is not active:
                overlay.clear_selection()

    def cancel(self):
        self.finish(None)

    def finish(self, image):
        if self._done:
            return
        self._done = True
        for overlay in self._overlays:
            overlay.close()
            overlay.deleteLater()
        self.finished.emit(image)
