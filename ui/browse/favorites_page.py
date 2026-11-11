# ui/browse/favorites_page.py
import os
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QMenu
from PySide6.QtCore import Qt, Signal

from services.db_handler import get_favorites, set_favorite, get_image_id_by_path
from ui.browse.image_grid import ImageGrid


class FavoritesPage(QWidget):
    image_activated = Signal(list, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._hint = QLabel(
            "No favorites yet.\nOpen an image and click ♡ Favorite in the sidebar."
        )
        self._hint.setAlignment(Qt.AlignCenter)
        self._hint.setStyleSheet("color: #999; font-size: 13px; padding: 24px;")
        layout.addWidget(self._hint)

        self._grid = ImageGrid()
        self._grid.image_activated.connect(self.image_activated)
        self._grid.image_context_menu.connect(self._on_menu)
        layout.addWidget(self._grid, stretch=1)

    def refresh(self) -> None:
        paths = [p for p in get_favorites() if os.path.exists(p)]
        self._grid.set_paths(paths)
        self._hint.setVisible(not paths)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.refresh()   # picks up changes made in the canvas

    def _on_menu(self, path: str, global_pos) -> None:
        menu = QMenu(self)
        action = menu.addAction("Remove from favorites")
        if menu.exec(global_pos) == action:
            image_id = get_image_id_by_path(path)
            if image_id:
                set_favorite(image_id, False)
                self.refresh()