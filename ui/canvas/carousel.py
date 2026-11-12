# ui/canvas/carousel.py
from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QScrollArea, QSizePolicy
from PySide6.QtGui import QPixmap, QIcon
from PySide6.QtCore import QSize, Qt

from services.thumb_cache import get_or_create_thumbnail

THUMB_SIZE = 64           # size of non-focused thumbnails
FOCUS_SIZE = 96           # size of the centered/current thumbnail
CAROUSEL_HEIGHT = 130     # total height of the whole carousel widget


class CarouselWidget(QWidget):
    """Horizontal scrollable thumbnail strip."""

    def __init__(self, on_click, parent=None):
        super().__init__(parent)
        self._on_click = on_click  # callback: fn(index) -> None
        self._thumb_cache: dict[str, QPixmap] = {}  # square-cropped pixmaps, keyed by path

        self.setFixedHeight(CAROUSEL_HEIGHT)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self._container = QWidget()
        self._layout = QHBoxLayout(self._container)
        self._layout.setSpacing(5)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setAlignment(Qt.AlignCenter)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedHeight(CAROUSEL_HEIGHT)
        scroll.setWidget(self._container)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _cache_cropped(self, path: str, size: int) -> QPixmap:
        """Get a square pixmap for `path` at `size`, loading it at most once."""
        if path not in self._thumb_cache:
            # Use the on-disk 256px thumbnail instead of decoding the full-size image.
            # Much faster, and it avoids Qt's size limit on huge files.
            thumb_path = get_or_create_thumbnail(path)
            raw = QPixmap(thumb_path) if thumb_path else QPixmap()
            if raw.isNull():  # thumbnail failed: show a gray square instead of crashing
                raw = QPixmap(FOCUS_SIZE, FOCUS_SIZE)
                raw.fill(Qt.darkGray)
            self._thumb_cache[path] = _square_crop(raw, FOCUS_SIZE)
        cached = self._thumb_cache[path]
        if size == FOCUS_SIZE:
            return cached
        return cached.scaled(size, size, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)

    def _clear_buttons(self) -> None:
        """Remove all thumbnail buttons.

        deleteLater() asks Qt to delete each widget once it's safe. That matters
        here because refresh() is triggered by clicking one of these buttons, so
        we'd otherwise be destroying a button inside its own click handler.
        """
        for i in reversed(range(self._layout.count())):
            w = self._layout.itemAt(i).widget()
            if w:
                self._layout.removeWidget(w)
                w.hide()
                w.deleteLater()

    def refresh(self, image_paths: list[str], current_index: int) -> None:
        """Rebuild thumbnails around current_index, focusing the current one."""
        self._clear_buttons()

        start = max(0, current_index - 3)
        end = min(len(image_paths), current_index + 4)
        for idx in range(start, end):
            path = image_paths[idx]
            is_current = (idx == current_index)
            size = FOCUS_SIZE if is_current else THUMB_SIZE

            btn = QPushButton()
            btn.setIcon(QIcon(self._cache_cropped(path, size)))
            btn.setIconSize(QSize(size, size))
            btn.setFixedSize(size + 8, size + 8)  # padding for the border

            if is_current:
                btn.setStyleSheet("""
                    QPushButton {
                        border: 3px solid #5fa8ff;
                        border-radius: 6px;
                        background-color: #2a2a2a;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        border: 1px solid #444;
                        border-radius: 4px;
                        background-color: #1a1a1a;
                    }
                    QPushButton:hover {
                        border: 1px solid #666;
                    }
                """)

            btn.clicked.connect(lambda _checked=False, i=idx: self._on_click(i))
            self._layout.addWidget(btn)

    def clear(self) -> None:
        self.refresh([], 0)


def _square_crop(pixmap: QPixmap, size: int) -> QPixmap:
    """Crop the center square out of a pixmap, then scale it to size x size."""
    side = min(pixmap.width(), pixmap.height())
    x = (pixmap.width() - side) // 2
    y = (pixmap.height() - side) // 2
    cropped = pixmap.copy(x, y, side, side)
    return cropped.scaled(size, size, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)