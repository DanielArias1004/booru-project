# thumb_loader.py

from PySide6.QtCore import QRunnable, QObject, Signal
from PySide6.QtGui import QImage  # ← QImage not QPixmap (for speed)


class ThumbSignals(QObject):
    ready = Signal(int, str, QImage)


class ThumbLoader(QRunnable):

    def __init__(self, index: int, path: str, size: int):
        super().__init__()
        self.index = index
        self.path = path
        self.size = size
        self.signals = ThumbSignals()
        self.setAutoDelete(True)

    def run(self) -> None:
        from PySide6.QtCore import Qt

        # QImage is safe to create on any thread, unlike QPixmap
        raw = QImage(self.path)

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
        self.signals.ready.emit(self.index, self.path, cropped)