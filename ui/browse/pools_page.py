# ui/browse/pools_page.py
import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QInputDialog, QMessageBox, QMenu
)
from PySide6.QtCore import Qt, Signal

from services.db_handler import (
    get_pools, get_pool_images, create_pool, rename_pool, delete_pool,
    remove_image_from_pool, get_image_id_by_path
)
from ui.browse.image_grid import ImageGrid

NAME_ROLE = Qt.UserRole + 1


class PoolsPage(QWidget):
    """Spotify-style: pools list on the left, the selected pool's images on the right."""
    image_activated = Signal(list, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pool_id: int | None = None
        self._pool_name: str = ""
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # left column
        left = QWidget()
        left.setObjectName("poolsLeft")
        left.setFixedWidth(240)
        left.setStyleSheet("#poolsLeft { background: #161616; }")  # scoped: doesn't cascade
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(8, 8, 8, 8)
        left_layout.setSpacing(6)

        new_btn = QPushButton("＋  New Pool")
        new_btn.clicked.connect(self._new_pool)
        left_layout.addWidget(new_btn)

        self._list = QListWidget()
        self._list.setStyleSheet("""
            QListWidget { background: #161616; border: none; outline: none; }
            QListWidget::item { padding: 8px 10px; color: #ccc; }
            QListWidget::item:hover:!selected { background: #222; }
            QListWidget::item:selected { background: #2a3a52; color: white; }
        """)
        self._list.currentItemChanged.connect(self._on_pool_selected)
        left_layout.addWidget(self._list, stretch=1)
        root.addWidget(left)

        # right column
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 10, 16, 0)
        self._title = QLabel("No pool selected")
        self._title.setStyleSheet("font-size: 16px; font-weight: bold;")
        header_layout.addWidget(self._title)
        header_layout.addStretch()
        self._rename_btn = QPushButton("Rename")
        self._rename_btn.clicked.connect(self._rename_pool)
        self._delete_btn = QPushButton("Delete")
        self._delete_btn.clicked.connect(self._delete_pool)
        header_layout.addWidget(self._rename_btn)
        header_layout.addWidget(self._delete_btn)
        right_layout.addWidget(header)

        self._hint = QLabel()
        self._hint.setAlignment(Qt.AlignCenter)
        self._hint.setStyleSheet("color: #999; font-size: 13px; padding: 16px;")
        right_layout.addWidget(self._hint)

        self._grid = ImageGrid()
        self._grid.image_activated.connect(self.image_activated)
        self._grid.image_context_menu.connect(self._on_grid_menu)
        right_layout.addWidget(self._grid, stretch=1)
        root.addWidget(right, stretch=1)

    # — Data —

    def refresh(self) -> None:
        keep = self._pool_id
        pools = get_pools()
        self._list.blockSignals(True)       # don't fire selection events while rebuilding
        self._list.clear()
        select_row = 0
        for i, pool in enumerate(pools):
            item = QListWidgetItem(f"{pool['name']}   ·   {pool['count']}")
            item.setData(Qt.UserRole, pool["id"])
            item.setData(NAME_ROLE, pool["name"])
            self._list.addItem(item)
            if pool["id"] == keep:
                select_row = i
        self._list.blockSignals(False)
        if pools:
            self._list.setCurrentRow(select_row)   # fires _on_pool_selected
        else:
            self._pool_id, self._pool_name = None, ""
            self._show_current_pool()

    def _on_pool_selected(self, current, _previous) -> None:
        if current is None:
            self._pool_id, self._pool_name = None, ""
        else:
            self._pool_id = current.data(Qt.UserRole)
            self._pool_name = current.data(NAME_ROLE)
        self._show_current_pool()

    def _show_current_pool(self) -> None:
        has_pool = self._pool_id is not None
        self._rename_btn.setEnabled(has_pool)
        self._delete_btn.setEnabled(has_pool)
        if not has_pool:
            self._title.setText("No pool selected")
            self._grid.set_paths([])
            self._hint.setText("Create a pool with the ＋ New Pool button.")
            self._hint.setVisible(True)
            return
        paths = [p for p in get_pool_images(self._pool_id) if os.path.exists(p)]
        self._title.setText(self._pool_name)
        self._grid.set_paths(paths)
        self._hint.setText("This pool is empty.\nOpen an image and use the ＋ Pool button to add it.")
        self._hint.setVisible(not paths)

    # — Actions —

    def _new_pool(self) -> None:
        name, ok = QInputDialog.getText(self, "New Pool", "Pool name:")
        if not ok or not name.strip():
            return
        new_id = create_pool(name)
        if new_id is None:
            QMessageBox.warning(self, "New Pool", "That name is empty or already taken.")
            return
        self._pool_id = new_id
        self.refresh()

    def _rename_pool(self) -> None:
        if self._pool_id is None:
            return
        name, ok = QInputDialog.getText(self, "Rename Pool", "New name:", text=self._pool_name)
        if ok and name.strip():
            if not rename_pool(self._pool_id, name):
                QMessageBox.warning(self, "Rename Pool", "That name is already taken.")
            self.refresh()

    def _delete_pool(self) -> None:
        if self._pool_id is None:
            return
        reply = QMessageBox.question(
            self, "Delete Pool",
            f"Delete '{self._pool_name}'? The images themselves are not deleted."
        )
        if reply == QMessageBox.Yes:
            delete_pool(self._pool_id)
            self._pool_id = None
            self.refresh()

    def _on_grid_menu(self, path: str, global_pos) -> None:
        if self._pool_id is None:
            return
        menu = QMenu(self)
        action = menu.addAction("Remove from pool")
        if menu.exec(global_pos) == action:
            image_id = get_image_id_by_path(path)
            if image_id:
                remove_image_from_pool(self._pool_id, image_id)
                self.refresh()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.refresh()