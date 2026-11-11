# ui/browse/image_grid_model.py
import heapq
import os
from collections import OrderedDict

from PySide6.QtCore import (
    QAbstractListModel, QModelIndex, Qt, QSize,
    QObject, QRunnable, QThreadPool, QTimer, Signal
)
from PySide6.QtGui import QPixmap, QImage, QColor, QIcon

from services.thumb_cache import get_or_create_thumbnail

import logging
logger = logging.getLogger(__name__)

THUMB_SIZE_DEFAULT = 150
CACHE_PIXELS = 256      # thumbnails on disk are 256px; the view scales them down
MAX_IN_FLIGHT = 4       # how many thumbnails load at once


class _LoadSignals(QObject):
    """ONE of these lives for the whole life of the model.
    Worker threads emit through it; Qt delivers the signal safely
    to the main thread."""
    ready = Signal(int, QImage, int)   # row, image, generation


class _Generation:
    """Shared counter. When the list changes we bump it, and any task
    started under an older number sees it is stale and quits early.
    (Replaces the per-task cancel Event.)"""
    def __init__(self):
        self.value = 0


class _ThumbTask(QRunnable):
    def __init__(self, row: int, path: str, generation: int,
                 gen_ref: _Generation, signals: _LoadSignals):
        super().__init__()
        self.row = row
        self.path = path
        self.generation = generation
        self._gen_ref = gen_ref
        self._signals = signals
        self.setAutoDelete(True)

    def _stale(self) -> bool:
        return self._gen_ref.value != self.generation

    def run(self) -> None:
        if self._stale():
            return
        try:
            thumb_path = get_or_create_thumbnail(self.path)
            if self._stale():
                return
            img = QImage(thumb_path) if thumb_path else QImage()
            if img.isNull():
                img = QImage(CACHE_PIXELS, CACHE_PIXELS, QImage.Format_RGB32)
                img.fill(QColor("#333333"))
            else:
                img = img.convertToFormat(QImage.Format_RGB32)
        except Exception:
            logger.exception("Thumbnail task failed for %s", self.path)
            img = QImage(CACHE_PIXELS, CACHE_PIXELS, QImage.Format_RGB32)
            img.fill(QColor("#333333"))
        self._signals.ready.emit(self.row, img, self.generation)


class ImageGridModel(QAbstractListModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._paths: list[str] = []
        self._thumb_size: int = THUMB_SIZE_DEFAULT

        self._icon_cache: OrderedDict[int, QIcon] = OrderedDict()
        self._cache_limit = 400

        self._loading: set[int] = set()
        self._pending: list[tuple[int, int]] = []   # heap of (priority, row)
        self._pending_rows: set[int] = set()        # fast "is it queued?" check
        self._queue_center = 0

        self._gen = _Generation()
        self._signals = _LoadSignals(self)
        self._signals.ready.connect(self._on_loaded)

        pix = QPixmap(CACHE_PIXELS, CACHE_PIXELS)
        pix.fill(QColor("#2a2a2a"))
        self._placeholder_icon = QIcon(pix)

        self._dispatch_timer = QTimer(self)
        self._dispatch_timer.setSingleShot(True)
        self._dispatch_timer.setInterval(80)
        self._dispatch_timer.timeout.connect(self._dispatch_pending)

        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(MAX_IN_FLIGHT)

    # — QAbstractListModel interface —

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._paths)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid() or index.row() >= len(self._paths):
            return None
        row = index.row()

        if role == Qt.DecorationRole:
            icon = self._icon_cache.get(row)
            return icon if icon is not None else self._placeholder_icon

        if role == Qt.SizeHintRole:
            s = self._thumb_size + 4
            return QSize(s, s)

        if role == Qt.ToolTipRole:
            return os.path.basename(self._paths[row])

        return None

    # — Public API —

    def set_paths(self, paths: list[str]) -> None:
        self._reset_loading_state()
        self.beginResetModel()
        self._paths = paths
        self.endResetModel()

    def set_thumb_size(self, size: int) -> None:
        # Thumbnails are cached at 256px and the view scales them to its
        # iconSize, so a size change needs NO reloading. Just remember it.
        self._thumb_size = size

    def path_at(self, row: int) -> str:
        return self._paths[row] if 0 <= row < len(self._paths) else ""

    def all_paths(self) -> list[str]:
        return list(self._paths)

    def prioritize_visible(self, first: int, last: int) -> None:
        self._pending.clear()
        self._pending_rows.clear()
        self._queue_center = (first + last) // 2

    def request_thumbnail(self, row: int) -> None:
        if not (0 <= row < len(self._paths)):
            return
        if row in self._icon_cache or row in self._loading or row in self._pending_rows:
            return
        heapq.heappush(self._pending, (abs(row - self._queue_center), row))
        self._pending_rows.add(row)
        if not self._dispatch_timer.isActive():
            self._dispatch_timer.start()

    # — Internal —

    def _reset_loading_state(self) -> None:
        self._gen.value += 1          # invalidates every task already queued/running
        self._pool.clear()            # drops tasks that haven't started yet
        self._icon_cache.clear()
        self._loading.clear()
        self._pending.clear()
        self._pending_rows.clear()
        self._dispatch_timer.stop()

    def _dispatch_pending(self) -> None:
        while self._pending and len(self._loading) < MAX_IN_FLIGHT:
            _, row = heapq.heappop(self._pending)
            self._pending_rows.discard(row)
            if row >= len(self._paths) or row in self._icon_cache or row in self._loading:
                continue
            self._loading.add(row)
            task = _ThumbTask(row, self._paths[row], self._gen.value,
                              self._gen, self._signals)
            self._pool.start(task)

    def _on_loaded(self, row: int, image: QImage, generation: int) -> None:
        if generation != self._gen.value:
            return   # result from before the list/size changed: ignore
        self._loading.discard(row)
        self._icon_cache[row] = QIcon(QPixmap.fromImage(image))
        self._icon_cache.move_to_end(row)
        while len(self._icon_cache) > self._cache_limit:
            self._icon_cache.popitem(last=False)
        idx = self.index(row)
        self.dataChanged.emit(idx, idx, [Qt.DecorationRole])
        self._dispatch_pending()   # a slot just freed up, so refill immediately