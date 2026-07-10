# thumb_loader.py

from PySide6.QtCore import QRunnable, QObject, Signal
from PySide6.QtGui import QImage  # ← QImage not QPixmap (for speed)
import threading


class ThumbSignals(QObject):
    ready = Signal(int, str, QImage, int)  # index, path, QImage, generation


class ThumbLoader(QRunnable):

    def __init__(self, index: int, path: str, size: int, generation: int):
        super().__init__()
        self.index = index
        self.path = path
        self.size = size
        self.generation = generation
        self.signals = ThumbSignals()
        self.setAutoDelete(True)
        self._cancelled = threading.Event()  # thread-safe flag

    def cancel(self) -> None:
        """Signal this task to exit before doing any work."""
        self._cancelled.set()

    def run(self) -> None:
        if self._cancelled.is_set(): # check the flag before doing any expensive work
            return
        
        from PySide6.QtCore import Qt
        raw = QImage(self.path) # QImage is safe to create on any thread, unlike QPixmap (which is limited to the UI/main thread only)

        if self._cancelled.is_set():  # check again after the slow disk read
            return

        if raw.isNull():
            raw = QImage(self.size, self.size, QImage.Format_RGB32)
            raw.fill(0xFF333333)

        # square crop
        side = min(raw.width(), raw.height())
        x = (raw.width() - side) // 2
        y = (raw.height() - side) // 2
        cropped = raw.copy(x, y, side, side).scaled(
            self.size, self.size,
            Qt.IgnoreAspectRatio,
            Qt.SmoothTransformation
        )

        if self._cancelled.is_set():  # check once more before emitting (so it won't touch the grid after cancellation)
            return

        cropped = cropped.convertToFormat(QImage.Format_RGB32)  # ← pre-convert for faster fromImage
        self.signals.ready.emit(self.index, self.path, cropped, self.generation)