"""Programmatically drawn tool icons — no asset files needed."""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap

SIZE = 26


def _painter(pixmap, color, width=2.4):
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setPen(QPen(color, width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    return p


def make_icon(name, color):
    pixmap = QPixmap(SIZE, SIZE)
    pixmap.fill(Qt.transparent)
    c = QColor(color)
    p = _painter(pixmap, c)
    s = SIZE

    if name == "select":
        path = QPainterPath(QPointF(7, 4))
        for pt in [(7, 19), (11, 15.5), (14, 21.5), (16.5, 20.3),
                   (13.5, 14.5), (18.5, 14)]:
            path.lineTo(QPointF(*pt))
        path.closeSubpath()
        p.setBrush(c)
        p.drawPath(path)
    elif name == "arrow":
        p.setBrush(c)
        p.setPen(QPen(c, 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawLine(5, 21, 15, 11)
        head = QPainterPath(QPointF(21, 5))
        head.lineTo(QPointF(19.5, 14.5))
        head.lineTo(QPointF(11.5, 6.5))
        head.closeSubpath()
        p.setPen(Qt.NoPen)
        p.drawPath(head)
    elif name == "line":
        p.drawLine(5, 21, 21, 5)
    elif name == "rect":
        p.drawRect(QRectF(4.5, 6.5, 17, 13))
    elif name == "ellipse":
        p.drawEllipse(QRectF(4.5, 6.5, 17, 13))
    elif name == "pen":
        path = QPainterPath(QPointF(4, 21))
        path.cubicTo(QPointF(9, 10), QPointF(13, 22), QPointF(22, 6))
        p.drawPath(path)
    elif name == "text":
        font = QFont("Sans Serif", int(s * 0.62))
        font.setBold(True)
        p.setFont(font)
        p.drawText(QRectF(0, 0, s, s), Qt.AlignCenter, "A")
    elif name == "pixelate":
        p.setPen(Qt.NoPen)
        for i in range(4):
            for j in range(4):
                if (i + j) % 2 == 0:
                    col = QColor(c)
                    col.setAlpha(255 if (i + j) % 4 == 0 else 130)
                    p.setBrush(col)
                    p.drawRect(4 + i * 4.5, 4 + j * 4.5, 4.5, 4.5)
    elif name == "crop":
        p.drawLine(8, 3, 8, 18)
        p.drawLine(8, 18, 23, 18)
        p.drawLine(3, 8, 18, 8)
        p.drawLine(18, 8, 18, 23)
    elif name == "outline":
        p.setPen(QPen(QColor("#888888"), 5, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(6, 18, 20, 8)
        p.setPen(QPen(c, 2.4, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(6, 18, 20, 8)

    p.end()
    return QIcon(pixmap)


def make_color_icon(color, selected=False):
    pixmap = QPixmap(22, 22)
    pixmap.fill(Qt.transparent)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setBrush(QColor(color))
    p.setPen(QPen(QColor("#666666"), 1))
    p.drawEllipse(2, 2, 18, 18)
    if selected:
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor("#1E8FE1"), 2.5))
        p.drawEllipse(1, 1, 20, 20)
    p.end()
    return QIcon(pixmap)
