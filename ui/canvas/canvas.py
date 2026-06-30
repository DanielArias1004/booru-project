# viewer/canvas.py
import os
import random
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QTextEdit
)
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt

from services.db_handler import get_latest_note, add_note, get_image_id_by_path
from ui.canvas.carousel import CarouselWidget


class CanvasMixin:
    """Provides the Canvas tab UI and all image display/navigation logic."""

    def build_canvas_tab(self) -> QWidget:
        """Canvas: image & notes side-by-side, scrollable carousel, nav buttons."""
        tab = QWidget()
        v = QVBoxLayout(tab)

        # Top: image viewer + notes panel
        top = QHBoxLayout()

        # need a left panel here for tags like danbooru, gelbooru, etc. and a search bar for tags

        self.image_label = QLabel("No image loaded")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("background-color: #111;")
        self.image_label.setMinimumSize(600, 400)
        top.addWidget(self.image_label, stretch=3)

        # need to make notes not delete on every load
        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("Enter notes here…")
        self.notes_edit.setStyleSheet("background-color: #222; color: white;")
        self.notes_edit.setFixedWidth(250)
        top.addWidget(self.notes_edit, stretch=1)

        v.addLayout(top)

        # Carousel
        self.carousel = CarouselWidget(on_click=self._on_thumb_clicked)
        v.addWidget(self.carousel)

        # Navigation bar
            # can we add ability to type in the index you want?
        nav = QHBoxLayout()
        self.prev_btn = QPushButton("Previous")
        self.prev_btn.clicked.connect(self.show_previous)
        self.shuffle_btn = QPushButton("Random")
        self.shuffle_btn.clicked.connect(self.show_random)
        self.next_btn = QPushButton("Next")
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
            self.carousel.clear()
            return

        path = self.image_paths[self.current_index]
        rel_path = os.path.relpath(path, self.base_folder)

        pix = QPixmap(path) # loads a full resolution image into a qpixmap every time the user navigates to a new image.
            # we should scan paths eagerly but only decode/display images near the current index.
        if pix.isNull(): # File exists on disk but Qt couldn't decode it (corrupt, unsupported format, etc.)
            self.image_label.setText(f"Cannot display: {os.path.basename(path)}")
        else:
            self.image_label.setPixmap(
                pix.scaled(self.image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )

        image_id = get_image_id_by_path(rel_path)
        self.notes_edit.setText(get_latest_note(image_id) if image_id else "")

        filename = os.path.basename(path)
        self.index_label.setText(
            f"Image {self.current_index + 1} of {len(self.image_paths)} — {filename}"
        )

        self.carousel.refresh(self.image_paths, self.current_index)

    def resizeEvent(self, event):
        """Re-render the image when the window is resized."""
        super().resizeEvent(event) # super refers to the QMainWindow class in main_window.py, which the mixin is mixed into.
        if self.image_paths: # dont try to show image if there are no images loaded
            self.show_image()


    # — Navigation —

    def _on_thumb_clicked(self, idx: int) -> None:
        self._save_current_note() # can we instead use a timer to save it every few seconds if it's changed instead of in every function.
        self.current_index = idx
        self.show_image()

    def show_previous(self) -> None:
        self._save_current_note() # can we instead use a timer to save it every few seconds if it's changed instead of in every function.
        if self.image_paths:
            self.current_index = (self.current_index - 1) % len(self.image_paths)
            self.show_image()

    def show_next(self) -> None:
        self._save_current_note() # can we instead use a timer to save it every few seconds if it's changed instead of in every function.
        if self.image_paths:
            self.current_index = (self.current_index + 1) % len(self.image_paths)
            self.show_image()

    def show_random(self) -> None:
        self._save_current_note() # can we instead use a timer to save it every few seconds if it's changed instead of in every function.
        if self.image_paths:
            self.current_index = random.randrange(len(self.image_paths))
            self.show_image()

    # — Notes persistence —

    def _save_current_note(self) -> None:
        """Write the notes panel content to the DB for the current image."""
        if not self.image_paths:
            return
        path = self.image_paths[self.current_index]
        rel_path = os.path.relpath(path, self.base_folder)
        image_id = get_image_id_by_path(rel_path)
        if image_id:
            add_note(image_id, self.notes_edit.toPlainText(), datetime.now().isoformat())