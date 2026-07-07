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
    text = TextItem(QPointF(300, 50), QColor("#F5286E"), "Medium", True)
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
    text.set_style(size_name="Large")
    assert text.point_size == 40

    # Text edit flow: commit, discard-empty, cancel
    canvas._create_text(QPointF(50, 50))
    canvas._editing_text.set_text("typed")
    canvas.commit_text_edit()
    assert len(canvas.annotation_items()) == 6
    canvas._create_text(QPointF(60, 60))
    canvas.commit_text_edit()
    assert len(canvas.annotation_items()) == 6
    canvas._create_text(QPointF(70, 70))
    canvas._editing_text.set_text("nope")
    canvas.cancel_text_edit()
    assert len(canvas.annotation_items()) == 6

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
