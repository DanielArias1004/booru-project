# ui/browse/folder_tree.py
import os
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem
from PySide6.QtCore import Qt, Signal

PATH_ROLE = Qt.UserRole
LOADED_ROLE = Qt.UserRole + 1


class FolderTree(QTreeWidget):
    folder_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setMinimumWidth(180)
        self.setStyleSheet("""
            QTreeWidget { background: #161616; border: none; outline: none; color: #ccc; }
            QTreeWidget::item { padding: 4px 2px; }
            QTreeWidget::item:hover:!selected { background: #222; }
            QTreeWidget::item:selected { background: #2a3a52; color: white; }
        """)
        self.itemExpanded.connect(self._on_expanded)
        self.currentItemChanged.connect(self._on_current_changed)

    def reload(self, base_folders: list[str]) -> None:
        self.clear()
        for base in base_folders:
            if os.path.isdir(base):
                label = os.path.basename(base.rstrip("/\\")) or base
                self.addTopLevelItem(self._make_item(base, label))
        if self.topLevelItemCount():
            self.setCurrentItem(self.topLevelItem(0))   # triggers folder_selected

    def _make_item(self, path: str, label: str) -> QTreeWidgetItem:
        item = QTreeWidgetItem([label])
        item.setData(0, PATH_ROLE, os.path.normpath(path))
        item.setData(0, LOADED_ROLE, False)
        item.setToolTip(0, path)
        # show an expand arrow even though we haven't loaded the children yet
        item.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)
        return item

    def _on_expanded(self, item: QTreeWidgetItem) -> None:
        if item.data(0, LOADED_ROLE):
            return
        item.setData(0, LOADED_ROLE, True)
        try:
            with os.scandir(item.data(0, PATH_ROLE)) as it:
                dirs = sorted(
                    (e for e in it if e.is_dir() and not e.name.startswith(".")),
                    key=lambda e: e.name.lower()
                )
        except OSError:
            dirs = []
        for e in dirs:
            item.addChild(self._make_item(e.path, e.name))
        if not dirs:
            item.setChildIndicatorPolicy(QTreeWidgetItem.DontShowIndicator)

    def _on_current_changed(self, current, _previous) -> None:
        if current is not None:
            self.folder_selected.emit(current.data(0, PATH_ROLE))