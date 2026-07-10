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
MAX_CONCURRENT = 8  # never decode more than this many images simultaneously
BATCH_SIZE = MAX_CONCURRENT  # images loaded per scroll batch


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
        self._load_generation: int = 0  # increments every time we start a fresh load. helps us ignore stale background tasks that finish after a new load has started.
        
        self._active_tasks: list[ThumbLoader] = []  # track in-flight tasks for cancellation

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
        self._cancel_all_tasks()  # ← stop everything in flight
        self._load_generation += 1  # ← invalidate all in-flight tasks
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
        if self._loaded_count >= len(self._all_paths): # all images loaded — nothing more to do
            return
        if self._pending >= MAX_CONCURRENT: # too much work in flight already — wait for some to finish
            return

        end = min(self._loaded_count + BATCH_SIZE, len(self._all_paths))

        for i in range(self._loaded_count, end):
            path = self._all_paths[i]

            if path in self._thumb_cache:
                # already decoded from a previous session or size change
                self._add_thumb_to_grid(i, path, self._thumb_cache[path])
                continue

            # dispatch to background thread
            task = ThumbLoader(i, path, self._thumb_size, self._load_generation)
            task.signals.ready.connect(self._on_thumb_ready)
            self._active_tasks.append(task)
            self._pending += 1
            self._pool.start(task)

        self._loaded_count = end

    def _cancel_all_tasks(self) -> None:
        """Cancel all in-flight and queued tasks."""
        for task in self._active_tasks:
            try:
                task.signals.ready.disconnect(self._on_thumb_ready)
            except RuntimeError:
                pass  # already disconnected
            task.cancel()
        self._active_tasks.clear()
        self._pending = 0

    def _make_thumb_button(self, path: str, index: int) -> QPushButton:
        """Create a single thumbnail button for the grid. You can click these buttons to enter canvas view."""
        if path not in self._thumb_cache: # decode and cache the thumbnail if we haven't already
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
    def _on_thumb_ready(self, index: int, path: str, image: QImage, generation: int) -> None:
        if generation != self._load_generation: # old generation, ignore
            return
            
        self._pending = max(0, self._pending - 1)

        # remove this task from active list now that it's done
        self._active_tasks = [t for t in self._active_tasks if t.generation == self._load_generation]
        
        # convert to QPixmap here, on the main thread
        pixmap = QPixmap.fromImage(image)
        self._thumb_cache[path] = pixmap
        self._add_thumb_to_grid(index, path, pixmap)

        if self._pending == 0:
            self._fill_viewport_if_needed()
            # after a batch finishes, check if we're still near the bottom and need more.
            bar = self._scroll.verticalScrollBar()
            if bar.maximum() == 0: # no scrollbar yet
                return
            if bar.value() >= bar.maximum() - 300:
                self._load_timer.start()

    def _on_scroll(self, value: int) -> None:
        """Called every time the scroll position changes."""
        if self._pending > 0: # already loading, don't queue another batch yet
            return
        bar = self._scroll.verticalScrollBar()
        # if we're within 300px of the bottom, queue a batch load
        if value >= bar.maximum() - 300:
            # debounce: restart the timer instead of calling directly.
            # this prevents _load_next_batch from firing 20 times in one scroll gesture
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
        if size == self._thumb_size: # user clicked the already-active size
            return
        self._cancel_all_tasks()  # sets cancel flag on all tasks, clears list, sets _pending = 0
        self._load_generation += 1  # when a new load is started, invalidate all in-flight tasks by incrementing the generation counter
        self._thumb_size = size
        self._thumb_cache.clear() # cached pixmaps are no longer valid at the new size, clear them

        # clear all existing widgets from the grid
        for i in reversed(range(self._grid.count())):
            w = self._grid.itemAt(i).widget()
            if w:
                w.setParent(None)

        # reset and reload from scratch at the new size
        self._loaded_count = 0
        self._load_next_batch()
        # resizing instead of rebuilding the grid would be more efficient, but it's more complex to implement and not worth the effort for this prototype.

    def resizeEvent(self, event) -> None:
        """Reflow the grid when the window is resized."""
        super().resizeEvent(event)
        if not self.isVisible():  # don't reflow if we're not the active page
            return
        self._cancel_all_tasks()  # cancel any in-flight tasks, since the grid is about to be rebuilt
        self._load_generation += 1  # invalidate all in-flight tasks
        self._loaded_count = 0
        for i in reversed(range(self._grid.count())):
            w = self._grid.itemAt(i).widget()
            if w:
                w.setParent(None)
        self._load_next_batch() 