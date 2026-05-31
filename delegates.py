"""
Delegate personalizzati per QTreeWidget e QTableWidget.
"""

from PyQt6.QtWidgets import QStyledItemDelegate, QLineEdit, QComboBox
from PyQt6.QtCore import Qt


class _SelectAllDelegate(QStyledItemDelegate):
    """Delegate che seleziona tutto il testo quando si apre l'editor."""
    def createEditor(self, parent, option, index):
        editor = super().createEditor(parent, option, index)
        if isinstance(editor, QLineEdit):
            editor.setAutoFillBackground(True)
        return editor

    def setEditorData(self, editor, index):
        super().setEditorData(editor, index)
        if isinstance(editor, QLineEdit):
            editor.selectAll()


class _DayFrameDelegate(QStyledItemDelegate):
    """Delegate per DayFrame: QLineEdit su Qtà, QComboBox su NOVA."""

    def __init__(self, qty_col: int, nova_col: int, parent=None):
        super().__init__(parent)
        self._qty_col = qty_col
        self._nova_col = nova_col

    def createEditor(self, parent, option, index):
        col = index.column()
        if col == self._qty_col:
            editor = super().createEditor(parent, option, index)
            if isinstance(editor, QLineEdit):
                editor.setAutoFillBackground(True)
            return editor
        if col == self._nova_col:
            cb = QComboBox(parent)
            cb.addItems(["—", "1", "2", "3", "4"])
            cb.setAutoFillBackground(True)
            return cb
        return None

    def setEditorData(self, editor, index):
        if index.column() == self._nova_col and isinstance(editor, QComboBox):
            txt = index.data(Qt.ItemDataRole.DisplayRole) or "—"
            i = editor.findText(txt)
            editor.setCurrentIndex(max(i, 0))
        else:
            super().setEditorData(editor, index)
            if isinstance(editor, QLineEdit):
                editor.selectAll()

    def setModelData(self, editor, model, index):
        if index.column() == self._nova_col and isinstance(editor, QComboBox) and model:
            model.setData(index, editor.currentText(), Qt.ItemDataRole.EditRole)
        else:
            super().setModelData(editor, model, index)
