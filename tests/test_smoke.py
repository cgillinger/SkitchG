"""Offscreen smoke test covering the SkitchG core pipeline.

Run with:  python tests/test_smoke.py   (or pytest)
"""

import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QPointF, QRect, QRectF  # noqa: E402
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

from skitchg.commands import AddItemCommand, CropCommand  # noqa: E402
from skitchg.export import render_annotated  # noqa: E402
from skitchg.items import (  # noqa: E402
    ArrowItem,
    EllipseItem,
    MarkerItem,
    PixelateItem,
    RectItem,
    TextItem,
)
from skitchg.main_window import MainWindow  # noqa: E402


def test_smoke():
    workdir = tempfile.mkdtemp(prefix="skitchg-test-")

    img = QImage(800, 600, QImage.Format_ARGB32_Premultiplied)
    img.fill(QColor("#DDEEFF"))
    p = QPainter(img)
    p.fillRect(100, 100, 300, 200, QColor("#446688"))
    p.end()
    test_path = os.path.join(workdir, "test_input.jpg")
    assert img.save(test_path, "JPEG", 95)

    win = MainWindow()
    assert win.load_file(test_path, confirm=False)
    canvas = win.canvas
    stack = canvas.undo_stack
    assert canvas.base_image().width() == 800

    # Add one of each annotation type through the undo stack.
    arrow = ArrowItem(QPointF(150, 150), QPointF(400, 350), QColor("#F5286E"), 8.0, True)
    canvas.scene().addItem(arrow)
    stack.push(AddItemCommand(canvas, arrow))
    rect = RectItem(QRectF(450, 100, 200, 120), QColor("#1E8FE1"), 8.0, True)
    canvas.scene().addItem(rect)
    stack.push(AddItemCommand(canvas, rect))
    ell = EllipseItem(QRectF(100, 400, 180, 120), QColor("#39B54A"), 8.0, True)
    canvas.scene().addItem(ell)
    stack.push(AddItemCommand(canvas, ell))
    text = TextItem(QPointF(300, 50), QColor("#F5286E"), 28, True)
    text.set_text("Hello SkitchG")
    canvas.scene().addItem(text)
    stack.push(AddItemCommand(canvas, text, "Add text"))
    pix = PixelateItem(QRectF(500, 400, 150, 100), canvas.base_image, QColor("#000"), 8.0)
    canvas.scene().addItem(pix)
    stack.push(AddItemCommand(canvas, pix))
    assert len(canvas.annotation_items()) == 5

    # Undo/redo
    stack.undo()
    stack.undo()
    assert len(canvas.annotation_items()) == 3
    stack.redo()
    stack.redo()
    assert len(canvas.annotation_items()) == 5

    # Geometry state roundtrip
    old = arrow.get_state()
    arrow.set_points(QPointF(0, 0), QPointF(100, 100))
    arrow.set_state(old)
    assert arrow.end == QPointF(400, 350)

    # Style changes
    arrow.set_style(color=QColor("#39B54A"), stroke_width=14.0)
    assert arrow.color == QColor("#39B54A") and arrow.stroke_width == 14.0
    text.set_style(point_size=40)
    assert text.point_size == 40

    # Text edit flow: commit, discard-empty, cancel
    canvas._create_text(QPointF(50, 50))
    canvas._editing_text.set_text("typed")
    committed = canvas._editing_text
    canvas.commit_text_edit()
    assert len(canvas.annotation_items()) == 6
    # Fresh text stays selected → wheel resizes it right after typing
    assert committed.isSelected()
    size_before = committed.point_size
    canvas.adjust_size(+120)
    assert committed.point_size > size_before
    canvas.undo_stack.undo()
    assert committed.point_size == size_before
    canvas._create_text(QPointF(60, 60))
    canvas.commit_text_edit()
    assert len(canvas.annotation_items()) == 6
    canvas._create_text(QPointF(70, 70))
    canvas._editing_text.set_text("nope")
    canvas.cancel_text_edit()
    assert len(canvas.annotation_items()) == 6

    # Numbered markers: auto-increment, aiming, style and edit roundtrip
    assert canvas._next_marker_number() == 1
    m1 = MarkerItem(QPointF(200, 200), QColor("#F5286E"), 20.0, text="1")
    canvas.scene().addItem(m1)
    stack.push(AddItemCommand(canvas, m1))
    assert canvas._next_marker_number() == 2
    import math
    m1.set_geometry(head=QPointF(260, 160))  # far away: clamped to pin band
    d = math.hypot(m1.head.x() - m1.tip.x(), m1.head.y() - m1.tip.y())
    assert m1.radius * 1.4 <= d <= m1.radius * 2.0
    assert m1.head.x() > m1.tip.x() and m1.head.y() < m1.tip.y()  # aim kept
    m1.set_geometry(head=QPointF(201, 200))  # too close: pushed out to min
    d = math.hypot(m1.head.x() - m1.tip.x(), m1.head.y() - m1.tip.y())
    assert d >= m1.radius * 1.4
    m1.set_style(radius=28.0)
    assert m1.radius == 28.0
    state = m1.get_state()
    m1.set_text("12")
    m1.set_state(state)
    assert m1.text == "1"
    stack.undo()
    assert canvas._next_marker_number() == 1
    stack.redo()

    # Crop with undo/redo
    stack.push(CropCommand(canvas, QRect(50, 50, 500, 400)))
    assert canvas.base_image().width() == 500
    assert arrow.pos() == QPointF(-50, -50)
    stack.undo()
    assert canvas.base_image().width() == 800
    assert arrow.pos() == QPointF(0, 0)

    # Export: arrow pixels present in the flattened image
    out = render_annotated(canvas)
    assert out is not None and out.size() == canvas.base_image().size()
    assert any(
        out.pixelColor(int(150 + 250 * t), int(150 + 200 * t)) == QColor("#39B54A")
        for t in (0.3, 0.5, 0.7)
    )
    assert out.save(os.path.join(workdir, "out.png"), "PNG")
    assert out.save(os.path.join(workdir, "out.jpg"), "JPEG", 95)

    # Resolution-relative sizing: small image → scale 1, big photo → bigger
    assert canvas.image_scale == 1.0  # 800x600 diagonal = 1000 < 1200
    big = QImage(4000, 3000, QImage.Format_ARGB32_Premultiplied)
    big.fill(QColor("#FFFFFF"))
    big_path = os.path.join(workdir, "big.png")
    assert big.save(big_path)
    win2 = MainWindow()
    assert win2.load_file(big_path, confirm=False)
    c2 = win2.canvas
    assert abs(c2.image_scale - 5000 / 1200) < 0.01
    medium = c2.stroke_width()
    assert medium > 20  # ~25 px on a 4000x3000 image, clearly visible

    # On-the-fly resize: wheel scales pending style and selection relatively
    a2 = ArrowItem(QPointF(100, 100), QPointF(600, 600), QColor("#F5286E"),
                   medium, True)
    c2.scene().addItem(a2)
    c2.undo_stack.push(AddItemCommand(c2, a2))
    a2.setSelected(True)
    before = a2.stroke_width
    c2.adjust_size(+120)
    c2.adjust_size(+120)
    assert a2.stroke_width > before * 1.2
    assert c2.size_multiplier > 1.2
    assert c2.undo_stack.count() == 2  # wheel steps merged into one command
    c2.undo_stack.undo()
    assert a2.stroke_width == before

    # Handle drag must win over drawing tools (regression: grabbing a handle
    # with the arrow tool active used to create a new arrow instead).
    from PySide6.QtCore import QPoint, Qt as _Qt
    from PySide6.QtTest import QTest
    win3 = MainWindow()
    win3.resize(900, 700)
    win3.show()
    img3 = QImage(800, 600, QImage.Format_ARGB32_Premultiplied)
    img3.fill(QColor("#FFFFFF"))
    p3 = os.path.join(workdir, "plain.png")
    assert img3.save(p3)
    assert win3.load_file(p3, confirm=False)
    c3 = win3.canvas
    a3 = ArrowItem(QPointF(200, 200), QPointF(500, 400), QColor("#F5286E"), 10.0, False)
    c3.scene().addItem(a3)
    c3.undo_stack.push(AddItemCommand(c3, a3))
    c3.set_tool("arrow")
    a3.setSelected(True)  # handles appear
    app.processEvents()
    n_items = len(c3.annotation_items())
    end_view = c3.mapFromScene(QPointF(500, 400))
    target = c3.mapFromScene(QPointF(560, 300))
    QTest.mousePress(c3.viewport(), _Qt.LeftButton, _Qt.NoModifier, end_view)
    QTest.mouseMove(c3.viewport(), QPoint(target.x(), target.y()))
    QTest.mouseRelease(c3.viewport(), _Qt.LeftButton, _Qt.NoModifier, target)
    app.processEvents()
    assert len(c3.annotation_items()) == n_items, "handle drag created a new item"
    assert (a3.end - QPointF(560, 300)).manhattanLength() < 20, "handle did not move endpoint"

    # Moving by grabbing the body must also work with a drawing tool active
    c3.scene().clearSelection()
    pos_before = QPointF(a3.pos())
    mid = c3.mapFromScene(QPointF(380, 250))  # on the shaft
    tgt = c3.mapFromScene(QPointF(460, 310))
    QTest.mousePress(c3.viewport(), _Qt.LeftButton, _Qt.NoModifier, mid)
    QTest.mouseMove(c3.viewport(), QPoint(tgt.x(), tgt.y()))
    QTest.mouseRelease(c3.viewport(), _Qt.LeftButton, _Qt.NoModifier, tgt)
    app.processEvents()
    assert len(c3.annotation_items()) == n_items, "body drag created a new item"
    moved = a3.pos() - pos_before
    assert moved.manhattanLength() > 100, "body drag did not move the arrow"
    c3.undo_stack.undo()
    assert a3.pos() == pos_before, "move undo failed"

    # Highlighter: wide translucent stroke, tints but never hides the image
    from skitchg.items import HighlightItem
    hl = HighlightItem([QPointF(100, 500), QPointF(700, 500)],
                       QColor("#FFD400"), 10.0, False)
    c3.scene().addItem(hl)
    from skitchg.export import render_annotated as _render
    out3 = _render(c3)
    px = out3.pixelColor(400, 500)
    assert px != QColor("#FFFFFF") and px != QColor("#FFD400"), px.name()
    assert px.red() > 200 and px.blue() < 255, "not a translucent tint"

    # Save default path + clipboard
    assert win._default_save_path().endswith("test_input_annotated.png")
    win._write_image(win._default_save_path())
    assert os.path.exists(os.path.join(workdir, "test_input_annotated.png"))
    assert stack.isClean()
    win.copy_to_clipboard()
    assert not QGuiApplication.clipboard().image().isNull()


if __name__ == "__main__":
    test_smoke()
    print("ALL SMOKE TESTS PASSED")
