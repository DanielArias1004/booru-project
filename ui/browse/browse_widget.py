# ui/browse/browse_widget.py
import os
import math
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QScrollArea, QGridLayout, QLabel, QSizePolicy
)
from PySide6.QtGui import QPixmap, QIcon, QImage
from PySide6.QtCore import Qt, QSize, Signal, QTimer, QThreadPool

from services.config_handler import get_base_folders
from services.image_loader import load_images_from_folder
from ui.settings_dialog import SettingsDialog
from ui.browse.thumb_loader import ThumbLoader

# Thumbnail size presets (width and height in pixels)
THUMB_SIZES = {
    "small":  50,
    "medium": 150,
    "large":  250,
}

BATCH_SIZE = 50  # images loaded per scroll batch


class BrowseWidget(QWidget):
    # Signal emitted when user clicks an image.
    # Carries the full image path list and the clicked index
    # so canvas can show the right image with correct prev/next context.
    image_activated = Signal(list, int)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._all_paths: list[str] = [] # all discovered image paths
        self._loaded_count: int = 0 # how many thumbnails are rendered so far
        self._pending: int = 0 # how many background loads are currently in-flight
        self._thumb_size: int = THUMB_SIZES["medium"]
        self._thumb_cache: dict[str, QPixmap] = {} # stores QPixmap (converted on main thread) for each path

        self._pool = QThreadPool.globalInstance()  # shared thread pool for background tasks

        # We use a QTimer to debounce scroll events (only load more images after user stops scrolling for 100ms)
        self._load_timer = QTimer()
        self._load_timer.setSingleShot(True)
        self._load_timer.setInterval(100)  # 100ms debounce
        self._load_timer.timeout.connect(self._load_next_batch)

        self._build_ui()
        self.reload_images()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # — Top bar —
        top_bar = QHBoxLayout()

        # View size buttons (small / medium / large)
        # We use text labels for now; you could swap these for QIcons later
        for size_name, size_px in THUMB_SIZES.items():
            btn = QPushButton(size_name.capitalize())
            btn.setFixedHeight(28)
            # clicking captures size_px in a closure
            btn.clicked.connect(
                lambda _checked, s=size_px: self._set_thumb_size(s)
            )
            top_bar.addWidget(btn)

        top_bar.addStretch()  # pushes gear icon to the right

        # Gear / settings button
        gear_btn = QPushButton("⚙")
        gear_btn.setFixedSize(32, 32)
        gear_btn.setToolTip("Settings")
        gear_btn.clicked.connect(self._open_settings)
        top_bar.addWidget(gear_btn)

        layout.addLayout(top_bar)

        # — Scroll area containing the image grid —
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # This is the widget that actually holds the grid layout
        self._grid_container = QWidget()
        self._grid = QGridLayout(self._grid_container)
        self._grid.setSpacing(4)
        self._grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        self._scroll.setWidget(self._grid_container)
        layout.addWidget(self._scroll)

        # Connect scroll bar to our load-more logic
        self._scroll.verticalScrollBar().valueChanged.connect(self._on_scroll)

    def _open_settings(self) -> None:
        """Open the settings dialog. Reload images if folders changed."""
        dialog = SettingsDialog(parent=self)
        dialog.exec()  # blocks until dialog is closed
        # reload in case user added/removed base folders
        self.reload_images()

    def reload_images(self) -> None:
        """Re-scan all base folders and rebuild the grid from scratch."""
        self._all_paths = []
        for base in get_base_folders():
            if os.path.isdir(base):
                self._all_paths.extend(load_images_from_folder(base, base))
        self._all_paths.sort()

        # clear the grid and reset state
        self._loaded_count = 0
        self._thumb_cache.clear()
        for i in reversed(range(self._grid.count())):
            w = self._grid.itemAt(i).widget()
            if w:
                w.setParent(None)

        self._load_next_batch()

    def _load_next_batch(self) -> None:
        """Dispatch background load tasks for the next BATCH_SIZE images."""
        if self._loaded_count >= len(self._all_paths):
            # all images loaded — nothing more to do
            return
        if self._pending > 0:
            # already loading — don't stack up duplicate batches
            return

        end = min(self._loaded_count + BATCH_SIZE, len(self._all_paths))

        for i in range(self._loaded_count, end):
            path = self._all_paths[i]

            if path in self._thumb_cache:
                # already decoded from a previous session or size change
                self._add_thumb_to_grid(i, path, self._thumb_cache[path])
                continue

            # dispatch to background thread
            task = ThumbLoader(i, path, self._thumb_size)
            task.signals.ready.connect(self._on_thumb_ready)
            self._pending += 1
            self._pool.start(task)

        self._loaded_count = end

    def _make_thumb_button(self, path: str, index: int) -> QPushButton:
        """Create a single thumbnail button for the grid."""
        if path not in self._thumb_cache:
            raw = QPixmap(path)
            if raw.isNull():
                raw = QPixmap(self._thumb_size, self._thumb_size)
                raw.fill(Qt.darkGray)
            # square-crop, same logic as carousel
            side = min(raw.width(), raw.height())
            x = (raw.width() - side) // 2
            y = (raw.height() - side) // 2
            cropped = raw.copy(x, y, side, side).scaled(
                self._thumb_size, self._thumb_size,
                Qt.IgnoreAspectRatio, Qt.SmoothTransformation
            )
            self._thumb_cache[path] = cropped

        btn = QPushButton()
        btn.setIcon(QIcon(self._thumb_cache[path]))
        btn.setIconSize(QSize(self._thumb_size, self._thumb_size))
        btn.setFixedSize(self._thumb_size + 4, self._thumb_size + 4)
        btn.setStyleSheet("QPushButton { border: none; background: #1a1a1a; }"
                          "QPushButton:hover { border: 1px solid #5fa8ff; }")
        # emit signal with all paths + this image's index
        btn.clicked.connect(
            lambda _checked, i=index: self.image_activated.emit(self._all_paths, i)
        )
        return btn
    
    def _add_thumb_to_grid(self, index: int, path: str, pixmap: QPixmap) -> None:
        """Create a button for this thumbnail and place it in the grid."""
        available_width = self._scroll.viewport().width()
        cols = max(1, available_width // (self._thumb_size + 4))
        row = index // cols
        col = index % cols

        btn = QPushButton()
        btn.setIcon(QIcon(pixmap))
        btn.setIconSize(QSize(self._thumb_size, self._thumb_size))
        btn.setFixedSize(self._thumb_size + 4, self._thumb_size + 4)
        btn.setStyleSheet(
            "QPushButton { border: none; background: #1a1a1a; }"
            "QPushButton:hover { border: 1px solid #5fa8ff; }"
        )
        btn.clicked.connect(
            lambda _checked, i=index: self.image_activated.emit(self._all_paths, i)
        )
        self._grid.addWidget(btn, row, col)

    # _on_thumb_ready — receives QImage from worker, converts to QPixmap here on main thread
    def _on_thumb_ready(self, index: int, path: str, image: QImage) -> None:
        self._pending -= 1
        
        # convert to QPixmap here, on the main thread
        pixmap = QPixmap.fromImage(image)
        self._thumb_cache[path] = pixmap
        self._add_thumb_to_grid(index, path, pixmap)

        if self._pending == 0:
            self._fill_viewport_if_needed()

    def _on_scroll(self, value: int) -> None:
        """Called every time the scroll position changes."""
        bar = self._scroll.verticalScrollBar()
        # if we're within 300px of the bottom, queue a batch load
        if value >= bar.maximum() - 300:
            # debounce: restart the timer instead of calling directly.
            # this prevents _load_next_batch from firing 20 times
            # in one scroll gesture
            self._load_timer.start()

    def _fill_viewport_if_needed(self) -> None:
        """
        If the grid content is shorter than the visible area,
        load another batch immediately — no scrolling needed.
        
        This handles the case where 50 images don't fill a large window.
        """
        content_height = self._grid_container.sizeHint().height()
        viewport_height = self._scroll.viewport().height()

        if content_height < viewport_height and self._loaded_count < len(self._all_paths):
            self._load_next_batch()

    def _set_thumb_size(self, size: int) -> None:
        """Change the thumbnail size and rebuild the grid."""
        if size == self._thumb_size:
            return  # nothing to do — user clicked the already-active size
    
        self._thumb_size = size
        self._thumb_cache.clear() # cached pixmaps are no longer valid at the new size, clear them
        self._loaded_count = 0
        self._pending = 0  # abandon any in-flight loads (they'll be ignored when they arrive since cache is cleared)

        # instead of destroying widgets, just tell each one to resize and re-decode in the background at the new size
        for i in range(self._grid.count()):
            w = self._grid.itemAt(i).widget()
            if w:
                w.setFixedSize(size + 4, size + 4)
                w.setIconSize(QSize(size, size))

        # re-decode all visible thumbnails at new size in the background
        for i in range(self._loaded_count):
            path = self._all_paths[i]
            task = ThumbLoader(i, path, self._thumb_size)
            task.signals.ready.connect(self._on_thumb_ready)
            self._pending += 1
            self._pool.start(task)

    def resizeEvent(self, event) -> None:
        """Reflow the grid when the window is resized."""
        super().resizeEvent(event)
        # reflow by rebuilding — same as size change
        # we keep _thumb_cache so no re-decoding needed
        self._loaded_count = 0
        for i in reversed(range(self._grid.count())):
            w = self._grid.itemAt(i).widget()
            if w:
                w.setParent(None)
        self._load_next_batch()