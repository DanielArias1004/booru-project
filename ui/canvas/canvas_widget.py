# ui/canvas/canvas_widget.py
import os
import random
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QTextEdit
)
from PySide6.QtGui import QPixmap, QKeySequence, QShortcut, QMovie, QImageReader
from PySide6.QtCore import Qt, Signal, QSize

from services.db_handler import get_latest_note, add_note, get_image_id_by_path
from ui.canvas.carousel import CarouselWidget


class CanvasWidget(QWidget):
    # emitted when user wants to go back to browse
    back_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._image_paths: list[str] = []
        self._current_index: int = 0
        self._current_movie: QMovie | None = None
        self._base_folders: list[str] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Back button row
        top_bar = QHBoxLayout()
        back_btn = QPushButton("← Browse")
        back_btn.setFixedHeight(32)
        back_btn.clicked.connect(self._on_back)
        top_bar.addWidget(back_btn)
        top_bar.addStretch()
        layout.addLayout(top_bar)

        # Image + notes
        content = QHBoxLayout()
        self._image_label = QLabel("No image loaded")
        self._image_label.setAlignment(Qt.AlignCenter)
        self._image_label.setStyleSheet("background-color: #111;")
        self._image_label.setMinimumSize(600, 400)
        content.addWidget(self._image_label, stretch=3)

        self._notes_edit = QTextEdit()
        self._notes_edit.setPlaceholderText("Enter notes here…")
        self._notes_edit.setStyleSheet("background-color: #222; color: white;")
        self._notes_edit.setFixedWidth(250)
        content.addWidget(self._notes_edit, stretch=1)
        layout.addLayout(content)

        # Carousel
        self._carousel = CarouselWidget(on_click=self._on_thumb_clicked)
        layout.addWidget(self._carousel)

        # Nav bar
        nav = QHBoxLayout()
        prev_btn = QPushButton("⏮")
        prev_btn.setFixedSize(40, 40)
        prev_btn.clicked.connect(self.show_previous)

        shuffle_btn = QPushButton("🔀")
        shuffle_btn.setFixedSize(40, 40)
        shuffle_btn.clicked.connect(self.show_random)

        next_btn = QPushButton("⏭")
        next_btn.setFixedSize(40, 40)
        next_btn.clicked.connect(self.show_next)

        for btn in (prev_btn, shuffle_btn, next_btn):
            nav.addWidget(btn)

        nav.addSpacing(10)
        self._index_label = QLabel("No images loaded")
        self._index_label.setStyleSheet("font-weight: bold;")
        nav.addWidget(self._index_label)
        nav.addStretch()
        layout.addLayout(nav)

        # Keyboard shortcuts — scoped to this widget
        QShortcut(QKeySequence("Left"), self, self.show_previous)
        QShortcut(QKeySequence("Right"), self, self.show_next)

    def load(self, image_paths: list[str], index: int) -> None:
        """Called by main_window when an image is activated."""
        # this now passes paths directly.
        self._save_current_note()
        self._image_paths = image_paths
        self._current_index = index
        self._show_image()

    def _is_animated(self, path: str) -> bool: 
        """Check if a file has more than one frame (animated GIF or WebP)."""
        reader = QImageReader(path)
        return reader.imageCount() > 1

    def _show_image(self) -> None:
        if not self._image_paths:
            self._index_label.setText("No images loaded")
            self._image_label.setText("No image loaded")
            self._notes_edit.clear()
            self._carousel.clear()
            return

        path = self._image_paths[self._current_index]

        # Stop any currently playing animation before loading something new.
        # Otherwise the old QMovie keeps running and emitting frameChanged signals even after we've moved to a new image.
        if self._current_movie:
            self._current_movie.stop()
            self._current_movie = None

        # correct version of the animated branch:
        if self._is_animated(path):
            movie = QMovie(path)
            self._current_movie = movie

            # Read the natural size of the first frame so we can scale it
            reader = QImageReader(path)
            natural_size = reader.size()  # returns QSize(width, height)

            if natural_size.isValid():
                scaled = natural_size.scaled(
                    self._image_label.size(), Qt.KeepAspectRatio
                )
                movie.setScaledSize(scaled)

            self._image_label.setMovie(movie)
            movie.start()
        else:
            # Static image — use QPixmap as before
            self._current_movie = None
            pix = QPixmap(path)
            if pix.isNull():
                self._image_label.setText(f"Cannot display: {os.path.basename(path)}")
            else:
                self._image_label.setPixmap(
                    pix.scaled(self._image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )

        image_id = get_image_id_by_path(path)
        self._notes_edit.setText(get_latest_note(image_id) if image_id else "")

        filename = os.path.basename(path)
        self._index_label.setText(
            f"Image {self._current_index + 1} of {len(self._image_paths)} — {filename}"
        )
        self._carousel.refresh(self._image_paths, self._current_index)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if not self.isVisible():
            return
        if self._image_paths:
            self._show_image()

    def _on_back(self) -> None:
        self._save_current_note()
        self.back_requested.emit()

    def _on_thumb_clicked(self, idx: int) -> None:
        self._save_current_note()
        self._current_index = idx
        self._show_image()

    def show_previous(self) -> None:
        self._save_current_note()
        if self._image_paths:
            self._current_index = (self._current_index - 1) % len(self._image_paths)
            self._show_image()

    def show_next(self) -> None:
        self._save_current_note()
        if self._image_paths:
            self._current_index = (self._current_index + 1) % len(self._image_paths)
            self._show_image()

    def show_random(self) -> None:
        self._save_current_note()
        if self._image_paths:
            self._current_index = random.randrange(len(self._image_paths))
            self._show_image()

    def _save_current_note(self) -> None:
        if not self._image_paths:
            return
        path = self._image_paths[self._current_index]
        image_id = get_image_id_by_path(path)
        if image_id:
            add_note(image_id, self._notes_edit.toPlainText(), datetime.now().isoformat())