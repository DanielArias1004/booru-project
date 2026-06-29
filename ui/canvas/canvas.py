# viewer/canvas.py
import os
import random
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QTextEdit, QScrollArea
)
from PySide6.QtGui import QPixmap, QIcon
from PySide6.QtCore import Qt, QSize

from services.db_handler import get_latest_note, add_note, get_image_id_by_path


class CanvasMixin:
    """Provides the Canvas tab UI and all image display/navigation logic."""

    def build_canvas_tab(self) -> QWidget:
        """Canvas: image & notes side-by-side, scrollable carousel, nav buttons."""
        tab = QWidget()
        v = QVBoxLayout(tab)

        # Top: image viewer + notes panel
        top = QHBoxLayout()

        self.image_label = QLabel("No image loaded")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("background-color: #111;")
        self.image_label.setMinimumSize(600, 400)
        top.addWidget(self.image_label, stretch=3)

        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("Enter notes here…")
        self.notes_edit.setStyleSheet("background-color: #222; color: white;")
        self.notes_edit.setFixedWidth(250)
        top.addWidget(self.notes_edit, stretch=1)

        v.addLayout(top)

        # Thumbnail carousel
        self.carousel_container = QWidget()
        self.carousel_layout = QHBoxLayout(self.carousel_container)
        self.carousel_layout.setSpacing(5)
        self.carousel_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(self.carousel_container)
        scroll.setFixedHeight(120)
        v.addWidget(scroll)

        # Navigation bar
        nav = QHBoxLayout()
        self.prev_btn = QPushButton("⏮")
        self.prev_btn.clicked.connect(self.show_previous)
        self.shuffle_btn = QPushButton("🔀")
        self.shuffle_btn.clicked.connect(self.show_random)
        self.next_btn = QPushButton("⏭")
        self.next_btn.clicked.connect(self.show_next)

        for btn in (self.prev_btn, self.shuffle_btn, self.next_btn):
            btn.setFixedSize(40, 40)
            nav.addWidget(btn)

        nav.addSpacing(10)

        self.index_label = QLabel("No images loaded")
        self.index_label.setStyleSheet("font-weight: bold;")
        nav.addWidget(self.index_label)
        nav.addStretch()
        v.addLayout(nav)

        return tab

    # — Display —

    def show_image(self) -> None:
        """Render the current image, load its note, and refresh the carousel."""
        if not self.image_paths:
            self.index_label.setText("No images loaded")
            self.image_label.setText("No image loaded")
            self.notes_edit.clear()
            self._clear_carousel()
            return

        path = self.image_paths[self.current_index]

        pix = QPixmap(path)
        if pix.isNull():
            # File exists on disk but Qt couldn't decode it (corrupt, unsupported format, etc.)
            self.image_label.setText(f"Cannot display: {os.path.basename(path)}")
        else:
            self.image_label.setPixmap(
                pix.scaled(self.image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )

        image_id = get_image_id_by_path(path)
        self.notes_edit.setText(get_latest_note(image_id) if image_id else "")

        filename = os.path.basename(path)
        self.index_label.setText(
            f"Image {self.current_index + 1} of {len(self.image_paths)} — {filename}"
        )

        self._refresh_carousel()

    def _clear_carousel(self) -> None:
        """Remove all thumbnail widgets from the carousel."""
        for i in reversed(range(self.carousel_layout.count())):
            widget = self.carousel_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)

    def _refresh_carousel(self) -> None:
        """Rebuild thumbnails for the 5 images around the current one."""
        self._clear_carousel()
        start = max(0, self.current_index - 2)
        end = min(len(self.image_paths), self.current_index + 3)
        for idx in range(start, end):
            btn = QPushButton()
            btn.setIcon(QIcon(self.image_paths[idx]))
            btn.setIconSize(QSize(80, 80))
            btn.setFixedSize(84, 84)
            btn.clicked.connect(lambda _checked, i=idx: self._on_thumb_clicked(i))
            self.carousel_layout.addWidget(btn)

    # — Navigation —

    def _on_thumb_clicked(self, idx: int) -> None:
        self._save_current_note()
        self.current_index = idx
        self.show_image()

    def show_previous(self) -> None:
        self._save_current_note()
        if self.image_paths:
            self.current_index = (self.current_index - 1) % len(self.image_paths)
            self.show_image()

    def show_next(self) -> None:
        self._save_current_note()
        if self.image_paths:
            self.current_index = (self.current_index + 1) % len(self.image_paths)
            self.show_image()

    def show_random(self) -> None:
        self._save_current_note()
        if self.image_paths:
            self.current_index = random.randrange(len(self.image_paths))
            self.show_image()

    # — Notes persistence —

    def _save_current_note(self) -> None:
        """Write the notes panel content to the DB for the current image."""
        if not self.image_paths:
            return
        path = self.image_paths[self.current_index]
        image_id = get_image_id_by_path(path)
        if image_id:
            add_note(image_id, self.notes_edit.toPlainText(), datetime.now().isoformat())