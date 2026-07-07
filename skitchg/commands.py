"""Undo/redo commands for SkitchG."""

from PySide6.QtGui import QUndoCommand


class AddItemCommand(QUndoCommand):
    def __init__(self, canvas, item, text="Add annotation"):
        super().__init__(text)
        self.canvas = canvas
        self.item = item

    def redo(self):
        if self.item.scene() is None:
            self.canvas.scene().addItem(self.item)
        self.canvas.mark_dirty()

    def undo(self):
        self.item.setSelected(False)
        self.canvas.scene().removeItem(self.item)
        self.canvas.mark_dirty()


class RemoveItemsCommand(QUndoCommand):
    def __init__(self, canvas, items):
        super().__init__("Delete annotation")
        self.canvas = canvas
        self.items = list(items)

    def redo(self):
        for item in self.items:
            item.setSelected(False)
            self.canvas.scene().removeItem(item)
        self.canvas.mark_dirty()

    def undo(self):
        for item in self.items:
            self.canvas.scene().addItem(item)
        self.canvas.mark_dirty()


class MoveItemsCommand(QUndoCommand):
    def __init__(self, canvas, moves):
        """moves: list of (item, old_pos, new_pos)."""
        super().__init__("Move annotation")
        self.canvas = canvas
        self.moves = moves
        self._first = True

    def redo(self):
        if self._first:  # items are already at new_pos when pushed
            self._first = False
            return
        for item, _old, new in self.moves:
            item.setPos(new)
        self.canvas.mark_dirty()

    def undo(self):
        for item, old, _new in self.moves:
            item.setPos(old)
        self.canvas.mark_dirty()


class GeometryCommand(QUndoCommand):
    def __init__(self, canvas, item, old_state, new_state, text="Edit annotation"):
        super().__init__(text)
        self.canvas = canvas
        self.item = item
        self.old_state = old_state
        self.new_state = new_state
        self._first = True

    def redo(self):
        if self._first:
            self._first = False
            return
        self.item.set_state(self.new_state)
        self.canvas.mark_dirty()

    def undo(self):
        self.item.set_state(self.old_state)
        self.canvas.mark_dirty()


class StyleCommand(QUndoCommand):
    def __init__(self, canvas, items, new_style):
        """new_style: dict with any of color / stroke_width / outline."""
        super().__init__("Change style")
        self.canvas = canvas
        self.entries = [(item, item.get_style()) for item in items]
        self.new_style = new_style

    def redo(self):
        for item, _old in self.entries:
            item.set_style(**self.new_style)
        self.canvas.mark_dirty()

    def undo(self):
        for item, old in self.entries:
            item.set_style(**old)
        self.canvas.mark_dirty()


class CropCommand(QUndoCommand):
    def __init__(self, canvas, crop_rect):
        super().__init__("Crop")
        self.canvas = canvas
        self.crop_rect = crop_rect
        self.old_image = canvas.base_image()
        self.item_positions = [
            (item, item.pos()) for item in canvas.annotation_items()
        ]

    def redo(self):
        new_image = self.old_image.copy(self.crop_rect)
        self.canvas.set_base_image(new_image)
        dx, dy = self.crop_rect.x(), self.crop_rect.y()
        for item, old_pos in self.item_positions:
            item.setPos(old_pos.x() - dx, old_pos.y() - dy)
        self.canvas.mark_dirty()

    def undo(self):
        self.canvas.set_base_image(self.old_image)
        for item, old_pos in self.item_positions:
            item.setPos(old_pos)
        self.canvas.mark_dirty()
