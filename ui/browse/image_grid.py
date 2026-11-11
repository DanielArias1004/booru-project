# ui/browse/image_grid.py
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QListView, QAbstractItemView, QLabel
)
from PySide6.QtCore import Qt, Signal, QTimer, QSize, QPoint

from ui.browse.image_grid_model import ImageGridModel

THUMB_SIZES = {"small": 100, "medium": 150, "large": 250}


class ImageGrid(QWidget):
    """Thumbnail grid with size buttons and an image count. Reused by every page."""
    image_activated = Signal(list, int)        # all paths in the grid, row that was clicked
    image_context_menu = Signal(str, QPoint)   # path, global screen position

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thumb_size = THUMB_SIZES["medium"]
        self._retries = 0
        self._model = ImageGridModel(self)

        self._visible_timer = QTimer(self)
        self._visible_timer.setSingleShot(True)
        self._visible_timer.setInterval(50)
        self._visible_timer.timeout.connect(self._load_visible)

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self._top_bar = QHBoxLayout()
        for name, px in THUMB_SIZES.items():
            btn = QPushButton(name.capitalize())
            btn.setFixedHeight(28)
            btn.clicked.connect(lambda _checked=False, s=px: self._set_thumb_size(s))
            self._top_bar.addWidget(btn)
        self._top_bar.addStretch()
        self._count_label = QLabel("0 images")
        self._count_label.setStyleSheet("color: #999; font-size: 11px;")
        self._top_bar.addWidget(self._count_label)
        layout.addLayout(self._top_bar)

        self._view = QListView()
        self._view.setModel(self._model)
        self._view.setViewMode(QListView.IconMode)
        self._view.setResizeMode(QListView.Adjust)
        self._view.setUniformItemSizes(True)
        self._view.setSpacing(4)
        self._view.setMovement(QListView.Static)
        self._view.setSelectionMode(QAbstractItemView.SingleSelection)
        self._view.setWordWrap(False)
        self._view.setIconSize(QSize(self._thumb_size, self._thumb_size))
        self._view.setGridSize(QSize(self._thumb_size + 8, self._thumb_size + 8))
        self._view.setContextMenuPolicy(Qt.CustomContextMenu)
        self._view.setStyleSheet("""
            QListView { background-color: #111111; border: none; }
            QListView::item { background-color: #1a1a1a; border-radius: 2px; }
            QListView::item:hover { border: 2px solid #5fa8ff; }
            QListView::item:selected { border: 2px solid #ffffff; background-color: #2a2a2a; }
        """)
        self._view.clicked.connect(self._on_clicked)
        self._view.customContextMenuRequested.connect(self._on_context_menu)
        # lambda so the scroll position isn't passed into QTimer.start(msec)
        self._view.verticalScrollBar().valueChanged.connect(lambda _v: self._visible_timer.start())
        layout.addWidget(self._view, stretch=1)

    # — Public API —

    def add_toolbar_widget(self, widget: QWidget) -> None:
        """Put an extra widget (e.g. a checkbox) in the top bar, after the size buttons."""
        self._top_bar.insertWidget(len(THUMB_SIZES), widget)

    def set_paths(self, paths: list[str]) -> None:
        if paths == self._model.all_paths():
            return  # nothing changed, so don't reload anything
        self._model.set_paths(paths)
        self._count_label.setText(f"{len(paths)} images")
        self._retries = 0
        self._visible_timer.start()

    # — Internal —

    def _set_thumb_size(self, size: int) -> None:
        if size == self._thumb_size:
            return
        self._thumb_size = size
        self._model.set_thumb_size(size)
        self._view.setIconSize(QSize(size, size))
        self._view.setGridSize(QSize(size + 8, size + 8))
        self._visible_timer.start()

    def _on_clicked(self, index) -> None:
        self.image_activated.emit(self._model.all_paths(), index.row())

    def _on_context_menu(self, pos) -> None:
        index = self._view.indexAt(pos)
        if index.isValid():
            self.image_context_menu.emit(
                self._model.path_at(index.row()),
                self._view.viewport().mapToGlobal(pos)
            )

    def _visible_range(self) -> tuple[int, int]:
        """Probe a grid of points over the viewport and ask which item is under each."""
        vp = self._view.viewport()
        step = max(16, self._thumb_size // 2)
        first, last = -1, -1
        for y in range(4, vp.height(), step):
            for x in range(4, vp.width(), step):
                idx = self._view.indexAt(QPoint(x, y))
                if idx.isValid():
                    if first < 0:
                        first = idx.row()
                    last = max(last, idx.row())
        return first, last

    def _load_visible(self) -> None:
        count = self._model.rowCount()
        if count == 0:
            return
        first, last = self._visible_range()
        if first < 0:
            # layout isn't ready yet; try again shortly, but not forever
            if self._retries < 20:
                self._retries += 1
                QTimer.singleShot(100, self._load_visible)
            return
        self._retries = 0
        self._model.prioritize_visible(first, last)
        span = max(20, last - first + 1)   # also preload one screen above and below
        for row in range(max(0, first - span), min(count - 1, last + span) + 1):
            self._model.request_thumbnail(row)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._visible_timer.start()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._visible_timer.start()