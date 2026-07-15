# ui/browse/image_grid_model.py
import heapq
import os
from PySide6.QtCore import (
    QAbstractListModel, QModelIndex, Qt, QSize,
    QObject, QRunnable, QThreadPool, QTimer, Signal
)
from PySide6.QtGui import QPixmap, QImage, QColor, QIcon
import threading
from collections import OrderedDict

THUMB_SIZE_DEFAULT = 150
MAX_ACTIVE = 8

class _LoadSignals(QObject):
    ready = Signal(int, QImage, int)


class _ThumbTask(QRunnable):
    def __init__(self, row: int, path: str, size: int, generation: int):
        super().__init__()
        self.row = row
        self.path = path
        self.size = size
        self.generation = generation
        self.signals = _LoadSignals()
        self._cancelled = threading.Event()
        self.setAutoDelete(True)

    def cancel(self) -> None:
        self._cancelled.set()

    def run(self) -> None:
        if self._cancelled.is_set():
            return

        from services.thumb_cache import get_or_create_thumbnail
        thumb_path = get_or_create_thumbnail(self.path, self.size)

        if self._cancelled.is_set():
            return

        if thumb_path is None:
            # fallback: gray placeholder
            img = QImage(self.size, self.size, QImage.Format_RGB32)
            img.fill(QColor("#333333").rgb())
            self.signals.ready.emit(self.row, img, self.generation)
            return

        # load the tiny cached thumbnail — very fast
        img = QImage(thumb_path)
        if img.isNull():
            img = QImage(self.size, self.size, QImage.Format_RGB32)
            img.fill(QColor("#333333").rgb())

        if self._cancelled.is_set():
            return

        self.signals.ready.emit(self.row, img.convertToFormat(QImage.Format_RGB32), self.generation)


class ImageGridModel(QAbstractListModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._paths: list[str] = []
        self._thumb_size: int = THUMB_SIZE_DEFAULT
        self._pixmap_cache = OrderedDict()
        self._cache_limit = 300
        self._loading: set[int] = set()
        self._pending_requests = []
        self._queue_center = 0
        self._generation: int = 0
        self._active_tasks: list[_ThumbTask] = []

        # single placeholder icon reused for all unloaded cells
        self._placeholder_icon: QIcon = self._make_placeholder(THUMB_SIZE_DEFAULT)

        self._dispatch_timer = QTimer()
        self._dispatch_timer.setSingleShot(True)
        self._dispatch_timer.setInterval(80)
        self._dispatch_timer.timeout.connect(self._dispatch_pending)

        self._pool = QThreadPool()
        self._pool.setMaxThreadCount(4) # maybe even 2

    def _make_placeholder(self, size: int) -> QIcon:
        pix = QPixmap(size, size)
        pix.fill(QColor("#2a2a2a"))
        return QIcon(pix)

    # — QAbstractListModel interface —

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._paths)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid() or index.row() >= len(self._paths):
            return None
        row = index.row()

        if role == Qt.DecorationRole:
            if row in self._pixmap_cache:
                return QIcon(self._pixmap_cache[row])

            return self._placeholder_icon

        if role == Qt.SizeHintRole:
            s = self._thumb_size + 4
            return QSize(s, s)

        if role == Qt.ToolTipRole:
            return os.path.basename(self._paths[row])

        return None

    # — Public API —

    def request_thumbnail(self, row: int):
        self._request_load(row)

    def prioritize_visible(self, first: int, last: int):
        self._pending_requests.clear()

        center = (first + last) // 2

        # Store the current viewport center
        self._queue_center = center

    def set_paths(self, paths: list[str]) -> None:
        self._cancel_all()
        self._generation += 1
        self._pixmap_cache.clear()
        self._loading.clear()
        self.beginResetModel()
        self._paths = paths
        self.endResetModel()

    def set_thumb_size(self, size: int) -> None:
        if size == self._thumb_size:
            return
        self._cancel_all()
        self._generation += 1
        self._thumb_size = size
        self._pixmap_cache.clear()
        self._loading.clear()
        self._placeholder_icon = self._make_placeholder(size)
        if self._paths:
            self.dataChanged.emit(
                self.index(0),
                self.index(len(self._paths) - 1),
                [Qt.DecorationRole, Qt.SizeHintRole]
            )

    def path_at(self, row: int) -> str:
        return self._paths[row] if 0 <= row < len(self._paths) else ""

    def all_paths(self) -> list[str]:
        return list(self._paths)

    # — Internal —

    def _request_load(self, row: int):
        if row in self._pixmap_cache:
            return
        if row in self._loading:
            return
        for _, existing_row in self._pending_requests:
            if existing_row == row:
                return
        priority = abs(row - self._queue_center)
        heapq.heappush(
            self._pending_requests,
            (priority, row)
        )
        self._dispatch_timer.start()

    def _dispatch_pending(self):
        print("QUEUE SIZE:", len(self._pending_requests))
        available = MAX_ACTIVE - len(self._loading)
        if available <= 0:
            return
        while available > 0 and self._pending_requests:
            priority, row = heapq.heappop(
                self._pending_requests
            )

            if row in self._pixmap_cache:
                continue
            if row in self._loading:
                continue
            if row >= len(self._paths):
                continue

            self._loading.add(row)

            task = _ThumbTask(
                row,
                self._paths[row],
                self._thumb_size,
                self._generation,
            )

            task.signals.ready.connect(
                self._on_loaded
            )

            self._active_tasks.append(task)
            self._pool.start(task)
            available -= 1

    def _on_loaded(self, row: int, image: QImage, generation: int) -> None:
        if generation != self._generation:
            return
        self._loading.discard(row)
        self._pixmap_cache[row] = QPixmap.fromImage(image)
        self._pixmap_cache.move_to_end(row)
        while len(self._pixmap_cache) > self._cache_limit:
            self._pixmap_cache.popitem(last=False)
        idx = self.index(row)
        self.dataChanged.emit(idx, idx, [Qt.DecorationRole])
        self._dispatch_timer.start()

    def _cancel_all(self) -> None:
        for task in self._active_tasks:
            try:
                task.signals.ready.disconnect(self._on_loaded)
            except RuntimeError:
                pass
            task.cancel()
        self._active_tasks.clear()
        self._loading.clear()
        self._pending_requests.clear()
        self._dispatch_timer.stop()