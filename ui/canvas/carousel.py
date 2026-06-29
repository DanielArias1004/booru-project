# ui/canvas/carousel.py
from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QScrollArea
from PySide6.QtGui import QIcon
from PySide6.QtCore import QSize

class CarouselWidget(QWidget):
    """Horizontal scrollable thumbnail strip."""

    def __init__(self, on_click, parent=None):
        super().__init__(parent)
        # on_click is a callback: fn(index) -> None
        self._on_click = on_click

        self._container = QWidget()
        self._layout = QHBoxLayout(self._container)
        self._layout.setSpacing(5)
        self._layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedHeight(120)
        scroll.setWidget(self._container)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def refresh(self, image_paths: list[str], current_index: int) -> None:
        """Rebuild thumbnails around current_index."""
        # clear
        for i in reversed(range(self._layout.count())):
            w = self._layout.itemAt(i).widget()
            if w:
                w.setParent(None)

        start = max(0, current_index - 2)
        end = min(len(image_paths), current_index + 3)
        for idx in range(start, end):
            btn = QPushButton()
            btn.setIcon(QIcon(image_paths[idx]))
            btn.setIconSize(QSize(80, 80))
            btn.setFixedSize(84, 84)
            btn.clicked.connect(lambda _checked, i=idx: self._on_click(i))
            self._layout.addWidget(btn)

    def clear(self) -> None:
        self.refresh([], 0)