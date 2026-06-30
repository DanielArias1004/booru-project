# ui/canvas/carousel.py
from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QScrollArea, QSizePolicy
from PySide6.QtGui import QPixmap, QIcon
from PySide6.QtCore import QSize, Qt

THUMB_SIZE = 64           # size of non-focused thumbnails
FOCUS_SIZE = 96           # size of the centered/current thumbnail
CAROUSEL_HEIGHT = 130     # total height of the whole carousel widget

class CarouselWidget(QWidget):
    """Horizontal scrollable thumbnail strip."""

    def __init__(self, on_click, parent=None):
        super().__init__(parent)
        self._on_click = on_click # on_click is a callback: fn(index) -> None
        self._thumb_cache: dict[str, QPixmap] = {} # cache thumbnails (cropped sqaure) to avoid reloading from disk every time you change images

        self.setFixedHeight(CAROUSEL_HEIGHT)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed) # make the carousel expand horizontally but not vertically

        self._container = QWidget()
        self._layout = QHBoxLayout(self._container)
        self._layout.setSpacing(5)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setAlignment(Qt.AlignCenter) # center the thumbnails in the carousel

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedHeight(CAROUSEL_HEIGHT)
        scroll.setWidget(self._container)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _cache_cropped(self, path: str, size: int) -> QPixmap:
        """Get a square-cropped pixmap for path and store it in the cache at full FOCUS_SIZE."""
        if path not in self._thumb_cache:
            raw = QPixmap(path) # load the image from disk (this is slow, so we cache it)
            if raw.isNull(): # if the image failed to load (e.g. file not found, unsupported format), create a blank fallback pixmap to avoid crashing
                raw = QPixmap(FOCUS_SIZE, FOCUS_SIZE)
                raw.fill(Qt.darkGray)
            self._thumb_cache[path] = _square_crop(raw, FOCUS_SIZE) # crop and cache at full size and scale down later if needed. cheaper to crop once and scale later since cropping is more expensive. otherwise we would scale and then need to crop both the small and full quality images separately.
        cached = self._thumb_cache[path]
        if size == FOCUS_SIZE:
            return cached
        return cached.scaled(size, size, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)

    def refresh(self, image_paths: list[str], current_index: int) -> None:
        """Rebuild thumbnails around current_index, focusing the current one"""
        for i in reversed(range(self._layout.count())):
            w = self._layout.itemAt(i).widget()
            if w:
                w.setParent(None)

        # can we make the carousel expand based on the window width?
        start = max(0, current_index - 3)
        end = min(len(image_paths), current_index + 4)
        for idx in range(start, end): # for every image in the carousel
            path = image_paths[idx] # get the path for it
            is_current = (idx == current_index)
            if is_current: # if it's the current image, make it bigger
                size = FOCUS_SIZE
            else:
                size = THUMB_SIZE

            btn = QPushButton()
            btn.setIcon(QIcon(self._cache_cropped(path, size)))
            btn.setIconSize(QSize(size, size))
            btn.setFixedSize(size + 8, size + 8) # add padding around the thumbnail for the border

            if is_current:
                btn.setStyleSheet("""
                    QPushButton {
                        border: 3px solid #5fa8ff;
                        border-radius: 6px;
                        background-color: #2a2a2a;
                    }
                """)
            else: # maybe no border
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

            btn.clicked.connect(lambda _checked, i=idx: self._on_click(i))
            self._layout.addWidget(btn)

    def clear(self) -> None:
        self.refresh([], 0)

def _square_crop(pixmap: QPixmap, size: int) -> QPixmap:
    """Crop the center square out of a pixmap, then scale to size x size."""
    # we compute the largest centered square that fits in the original image (the pixmap), and crop it out.
    side = min(pixmap.width(), pixmap.height())
    x = (pixmap.width() - side) // 2 # center the crop
    y = (pixmap.height() - side) // 2 # center the crop
    cropped = pixmap.copy(x, y, side, side) # x and y are the center of the crop, side is the length of the square
    return cropped.scaled(size, size, Qt.IgnoreAspectRatio, Qt.SmoothTransformation) # finally scale it to target size with Qt.IgnoreAspectRatio (we can ignore aspect ratio since its a square now)