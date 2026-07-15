# ui/canvas/canvas_widget.py
import os
import random

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QFrame, QGraphicsOpacityEffect, QSplitter
)
from PySide6.QtGui import (
    QPixmap, QKeySequence, QShortcut, QPainter,
    QColor, QImageReader, QMovie
)
from PySide6.QtCore import (
    Qt, Signal, QTimer, QPropertyAnimation,
    QEasingCurve, QPointF, QRect
)

from services.db_handler import get_image_id_by_path
from ui.canvas.carousel import CarouselWidget

from ui.canvas.sidebar import CanvasSidebar


class ImageView(QWidget):
    """
    Replaces QLabel for image display.
    Supports zoom (scroll wheel), pan (drag), double-click to reset.
    For animated files, renders frames from a QMovie.
    """
    mouse_activity = Signal()   # emitted on any mouse interaction
    zoom_changed = Signal(float)  # emitted when zoom level changes

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap: QPixmap | None = None
        self._movie: QMovie | None = None
        self._zoom: float = 1.0
        self._pan: QPointF = QPointF(0, 0)
        self._drag_start: QPointF | None = None
        self._drag_pan_start: QPointF = QPointF(0, 0)
        self.setMouseTracking(True)
        self.setMinimumSize(400, 300)

    # — Public API —

    def set_pixmap(self, pixmap: QPixmap) -> None:
        self._stop_movie()
        self._pixmap = pixmap
        self._reset_view()
        self.update()

    def set_movie(self, movie: QMovie) -> None:
        self._stop_movie()
        self._movie = movie
        self._pixmap = None
        movie.frameChanged.connect(self.update)
        movie.start()
        self._reset_view()
        self.update()

    def stop_movie(self) -> None:
        self._stop_movie()

    def current_movie(self) -> QMovie | None:
        return self._movie

    def zoom_in(self) -> None:
        self._zoom = min(10.0, self._zoom * 1.2)
        self.zoom_changed.emit(self._zoom)
        self.update()

    def zoom_out(self) -> None:
        self._zoom = max(0.1, self._zoom / 1.2)
        self.zoom_changed.emit(self._zoom)
        self.update()

    def zoom_level(self) -> float:
        return self._zoom

    # — Internal —

    def _stop_movie(self) -> None:
        if self._movie:
            self._movie.stop()
            try:
                self._movie.frameChanged.disconnect(self.update)
            except RuntimeError:
                pass
            self._movie = None

    def _reset_view(self) -> None:
        self._zoom = 1.0
        self._pan = QPointF(0, 0)
        self.zoom_changed.emit(self._zoom)

    def _current_pixmap(self) -> QPixmap | None:
        if self._movie:
            return self._movie.currentPixmap()
        return self._pixmap

    def _display_rect(self, pix: QPixmap) -> QRect:
        """
        Calculate where to draw the pixmap given current zoom and pan.
        Base scale fits the image to the widget. Zoom multiplies that scale.
        Pan offsets the centered position.
        """
        if pix.isNull() or pix.width() == 0 or pix.height() == 0:
            return QRect()
        w, h = self.width(), self.height()
        pw, ph = pix.width(), pix.height()
        scale = min(w / pw, h / ph) * self._zoom
        dw = int(pw * scale)
        dh = int(ph * scale)
        x = int((w - dw) / 2 + self._pan.x())
        y = int((h - dh) / 2 + self._pan.y())
        return QRect(x, y, dw, dh)

    # — Qt overrides —

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#111111"))
        pix = self._current_pixmap()
        if pix and not pix.isNull():
            rect = self._display_rect(pix)
            if rect.isValid():
                painter.drawPixmap(rect, pix)

    def wheelEvent(self, event) -> None:
        self.mouse_activity.emit()
        factor = 1.1 if event.angleDelta().y() > 0 else 0.9
        self._zoom = max(0.1, min(10.0, self._zoom * factor))
        self.zoom_changed.emit(self._zoom)
        self.update()

    def mousePressEvent(self, event) -> None:
        self.mouse_activity.emit()
        if event.button() == Qt.LeftButton:
            self._drag_start = event.position()
            self._drag_pan_start = QPointF(self._pan)

    def mouseMoveEvent(self, event) -> None:
        self.mouse_activity.emit()
        if event.buttons() & Qt.LeftButton and self._drag_start is not None:
            self._pan = self._drag_pan_start + (event.position() - self._drag_start)
            self.update()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_start = None

    def mouseDoubleClickEvent(self, event) -> None:
        """Double-click resets zoom and pan to fit-to-window."""
        self._reset_view()
        self.update()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.update()


class FloatingControls(QFrame):
    """
    Semi-transparent control bar overlaid on ImageView.
    Fades in on mouse activity, fades out after 2s of inactivity.
    Pin button keeps it permanently visible.
    Works in fullscreen since it's a child of ImageView.
    """

    def __init__(self, callbacks: dict, parent=None):
        super().__init__(parent)
        self._callbacks = callbacks
        self._pinned: bool = False

        # Opacity animation
        self._effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._effect)
        self._effect.setOpacity(0.0)

        self._anim = QPropertyAnimation(self._effect, b"opacity")
        self._anim.setDuration(250)
        self._anim.setEasingCurve(QEasingCurve.InOutQuad)
        self._anim.finished.connect(self._on_anim_finished)

        # Auto-hide timer
        self._hide_timer = QTimer()
        self._hide_timer.setSingleShot(True)
        self._hide_timer.setInterval(2000)
        self._hide_timer.timeout.connect(self._fade_out)

        self._build_ui()
        # start invisible and non-interactive so it doesn't block clicks
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

    def _build_ui(self) -> None:
        self.setStyleSheet("""
            QFrame {
                background-color: rgba(0, 0, 0, 190);
                border-radius: 10px;
            }
            QPushButton {
                background: transparent;
                color: white;
                border: none;
                padding: 6px 10px;
                font-size: 15px;
                border-radius: 4px;
                min-width: 28px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 40);
            }
            QPushButton:checked {
                color: #5fa8ff;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(2)

        def sep() -> QLabel:
            s = QLabel("│")
            s.setStyleSheet("color: #555; padding: 0 4px;")
            return s

        # Navigation
        self._prev_btn = QPushButton("⏮")
        self._prev_btn.setToolTip("Previous (←)")
        self._prev_btn.clicked.connect(lambda: self._call('prev'))

        self._next_btn = QPushButton("⏭")
        self._next_btn.setToolTip("Next (→)")
        self._next_btn.clicked.connect(lambda: self._call('next'))

        # Playback — only visible for animated images
        self._frame_back_btn = QPushButton("⏪")
        self._frame_back_btn.setToolTip("Frame back (,)")
        self._frame_back_btn.clicked.connect(lambda: self._call('frame_back'))

        self._play_btn = QPushButton("⏸")
        self._play_btn.setToolTip("Play / Pause (Space)")
        self._play_btn.clicked.connect(lambda: self._call('play_pause'))

        self._frame_fwd_btn = QPushButton("⏩")
        self._frame_fwd_btn.setToolTip("Frame forward (.)")
        self._frame_fwd_btn.clicked.connect(lambda: self._call('frame_forward'))

        self._anim_sep = sep()

        # Zoom
        zoom_out_btn = QPushButton("−")
        zoom_out_btn.setToolTip("Zoom out (-)")
        zoom_out_btn.clicked.connect(lambda: self._call('zoom_out'))

        self._zoom_label = QLabel("100%")
        self._zoom_label.setAlignment(Qt.AlignCenter)
        self._zoom_label.setStyleSheet(
            "color: white; min-width: 48px; padding: 0; font-size: 12px;"
        )
        self._zoom_label.setToolTip("Double-click image to reset zoom")

        zoom_in_btn = QPushButton("+")
        zoom_in_btn.setToolTip("Zoom in (+)")
        zoom_in_btn.clicked.connect(lambda: self._call('zoom_in'))

        # Fullscreen
        self._fs_btn = QPushButton("⛶")
        self._fs_btn.setToolTip("Fullscreen (F11)")
        self._fs_btn.clicked.connect(lambda: self._call('toggle_fullscreen'))

        # Notes toggle
        notes_btn = QPushButton("📝")
        notes_btn.setToolTip("Toggle notes (N)")
        notes_btn.clicked.connect(lambda: self._call('toggle_notes'))

        # Pin
        self._pin_btn = QPushButton("📌")
        self._pin_btn.setCheckable(True)
        self._pin_btn.setToolTip("Pin — keep controls visible")
        self._pin_btn.clicked.connect(self._on_pin_clicked)

        # Assemble
        for widget in [
            self._prev_btn,
            self._frame_back_btn, self._play_btn, self._frame_fwd_btn,
            self._anim_sep,
            zoom_out_btn, self._zoom_label, zoom_in_btn,
            sep(), self._next_btn,
            sep(), self._fs_btn, notes_btn,
            sep(), self._pin_btn,
        ]:
            layout.addWidget(widget)

        self.set_animated(False)
        self.adjustSize()

    def _call(self, name: str) -> None:
        fn = self._callbacks.get(name)
        if fn:
            fn()

    # — Public API —

    def show_controls(self) -> None:
        """Show the bar and restart the auto-hide countdown."""
        self._fade_in()
        if not self._pinned:
            self._hide_timer.start()

    def set_animated(self, animated: bool) -> None:
        """Show playback controls only when current image is animated."""
        for w in (self._frame_back_btn, self._play_btn,
                  self._frame_fwd_btn, self._anim_sep):
            w.setVisible(animated)
        self.adjustSize()

    def set_playing(self, playing: bool) -> None:
        self._play_btn.setText("⏸" if playing else "▶")

    def set_zoom(self, zoom: float) -> None:
        self._zoom_label.setText(f"{int(zoom * 100)}%")

    def set_fullscreen(self, fullscreen: bool) -> None:
        self._fs_btn.setText("✕ Exit" if fullscreen else "⛶")

    # — Internal —

    def _fade_in(self) -> None:
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.raise_()
        self._anim.stop()
        self._anim.setStartValue(self._effect.opacity())
        self._anim.setEndValue(1.0)
        self._anim.start()

    def _fade_out(self) -> None:
        if self._pinned:
            return
        self._anim.stop()
        self._anim.setStartValue(self._effect.opacity())
        self._anim.setEndValue(0.0)
        self._anim.start()

    def _on_anim_finished(self) -> None:
        # when fully hidden, stop intercepting mouse/keyboard events
        if self._effect.opacity() == 0.0:
            self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

    def _on_pin_clicked(self, checked: bool) -> None:
        self._pinned = checked
        if not checked:
            # start the hide timer now that it's unpinned
            self._hide_timer.start()


class CanvasWidget(QWidget):
    """
    Full image viewer. Shown when user clicks an image in browse.
    Contains ImageView, FloatingControls, and carousel
    """
    back_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._image_paths: list[str] = []
        self._current_index: int = 0
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # — Top bar —
        self._top_bar = QWidget()
        self._top_bar.setStyleSheet("background: #1a1a1a;")
        top_layout = QHBoxLayout(self._top_bar)
        top_layout.setContentsMargins(8, 4, 8, 4)
        back_btn = QPushButton("← Browse")
        back_btn.setFixedHeight(30)
        back_btn.clicked.connect(self._on_back)
        top_layout.addWidget(back_btn)
        top_layout.addStretch()
        layout.addWidget(self._top_bar)

        # — Image + sidebar —
        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self._image_view = ImageView()
        self._image_view.mouse_activity.connect(self._on_mouse_activity)
        self._image_view.zoom_changed.connect(self._on_zoom_changed)
        content_layout.addWidget(self._image_view, stretch=1)

        # sidebar with resize handle
        self._sidebar = CanvasSidebar()
        self._sidebar_visible = True

        # QSizeGrip lets user drag to resize sidebar
        self._splitter = QSplitter(Qt.Horizontal)
        self._splitter.addWidget(self._image_view)
        self._splitter.addWidget(self._sidebar)
        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 0)
        self._splitter.setSizes([900, 280])
        self._splitter.setStyleSheet("""
            QSplitter::handle {
                background: #333;
                width: 2px;
            }
        """)

        content_layout.addWidget(self._splitter)
        layout.addWidget(content, stretch=1)

        # — Carousel —
        self._carousel = CarouselWidget(on_click=self._on_thumb_clicked)
        layout.addWidget(self._carousel)

        # — Nav bar —
        self._nav_bar = QWidget()
        self._nav_bar.setStyleSheet("background: #1a1a1a;")
        nav_layout = QHBoxLayout(self._nav_bar)
        nav_layout.setContentsMargins(8, 4, 8, 4)
        for icon, slot in [("⏮", self.show_previous),
                            ("🔀", self.show_random),
                            ("⏭", self.show_next)]:
            btn = QPushButton(icon)
            btn.setFixedSize(40, 40)
            btn.clicked.connect(slot)
            nav_layout.addWidget(btn)
        nav_layout.addSpacing(10)
        self._index_label = QLabel("No images loaded")
        self._index_label.setStyleSheet("font-weight: bold; color: white;")
        nav_layout.addWidget(self._index_label)
        nav_layout.addStretch()
        layout.addWidget(self._nav_bar)

        # — Floating controls (child of ImageView so it overlays it) —
        self._controls = FloatingControls(
            callbacks={
                'prev':             self.show_previous,
                'next':             self.show_next,
                'zoom_in':          self._image_view.zoom_in,
                'zoom_out':         self._image_view.zoom_out,
                'toggle_fullscreen': self._toggle_fullscreen,
                'toggle_notes':     self._toggle_notes,
                'play_pause':       self._play_pause,
                'frame_back':       self._frame_back,
                'frame_forward':    self._frame_forward,
            },
            parent=self._image_view  # overlay on the image, not the whole canvas
        )

        # — Keyboard shortcuts —
        QShortcut(QKeySequence("Left"),   self, self.show_previous)
        QShortcut(QKeySequence("Right"),  self, self.show_next)
        QShortcut(QKeySequence("F11"),    self, self._toggle_fullscreen)
        QShortcut(QKeySequence("Space"),  self, self._play_pause)
        QShortcut(QKeySequence("+"),      self, self._image_view.zoom_in)
        QShortcut(QKeySequence("-"),      self, self._image_view.zoom_out)
        QShortcut(QKeySequence("N"),      self, self._toggle_notes)
        QShortcut(QKeySequence("Escape"), self, self._on_escape)
        QShortcut(QKeySequence(","),      self, self._frame_back)
        QShortcut(QKeySequence("."),      self, self._frame_forward)

    # — Public interface —

    def load(self, image_paths: list[str], index: int) -> None:
        """Called by main_window when the user clicks an image in browse."""
        self._image_paths = image_paths
        self._current_index = index
        self._show_image()

    # — Image display —

    def _show_image(self) -> None:
        if not self._image_paths:
            self._index_label.setText("No images loaded")
            self._image_view.set_pixmap(QPixmap())
            self._carousel.clear()
            return

        path = self._image_paths[self._current_index]

        if self._is_animated(path):
            movie = QMovie(path)
            self._image_view.set_movie(movie)
            self._controls.set_animated(True)
            self._controls.set_playing(True)
        else:
            self._image_view.set_pixmap(QPixmap(path))
            self._controls.set_animated(False)

        self._index_label.setText(
            f"Image {self._current_index + 1} of {len(self._image_paths)}"
            f" — {os.path.basename(path)}"
        )

        self._carousel.refresh(self._image_paths, self._current_index)
        self._controls.set_zoom(self._image_view.zoom_level())
        self._reposition_controls()

        # load sidebar for current image
        self._sidebar.load_image(path)

    def _is_animated(self, path: str) -> bool:
        return QImageReader(path).imageCount() > 1
    
    def _toggle_notes(self) -> None:
        self._sidebar_visible = not self._sidebar_visible
        self._sidebar.setVisible(self._sidebar_visible)

    # — Navigation —

    def _on_thumb_clicked(self, idx: int) -> None:
        self._current_index = idx
        self._show_image()

    def show_previous(self) -> None:
        if self._image_paths:
            self._current_index = (self._current_index - 1) % len(self._image_paths)
            self._show_image()

    def show_next(self) -> None:
        if self._image_paths:
            self._current_index = (self._current_index + 1) % len(self._image_paths)
            self._show_image()

    def show_random(self) -> None:
        if self._image_paths:
            self._current_index = random.randrange(len(self._image_paths))
            self._show_image()

    # — Playback —

    def _play_pause(self) -> None:
        movie = self._image_view.current_movie()
        if movie is None:
            return
        if movie.state() == QMovie.Running:
            movie.setPaused(True)
            self._controls.set_playing(False)
        else:
            movie.setPaused(False)
            self._controls.set_playing(True)

    def _frame_back(self) -> None:
        movie = self._image_view.current_movie()
        if movie is None:
            return
        # pause first so the user sees the specific frame
        movie.setPaused(True)
        self._controls.set_playing(False)
        movie.jumpToFrame(max(0, movie.currentFrameNumber() - 1))

    def _frame_forward(self) -> None:
        movie = self._image_view.current_movie()
        if movie is None:
            return
        movie.setPaused(True)
        self._controls.set_playing(False)
        count = movie.frameCount()
        if count > 0:
            movie.jumpToFrame(
                (movie.currentFrameNumber() + 1) % count
            )

    # — Fullscreen —

    def _toggle_fullscreen(self) -> None:
        win = self.window()
        if win.isFullScreen():
            win.showNormal()
            self._set_fullscreen_ui(False)
        else:
            win.showFullScreen()
            self._set_fullscreen_ui(True)

    def _set_fullscreen_ui(self, fullscreen: bool) -> None:
        """
        In fullscreen: hide chrome, let the image fill everything.
        The floating controls become the primary way to interact.
        """
        self._top_bar.setVisible(not fullscreen)
        self._carousel.setVisible(not fullscreen)
        self._nav_bar.setVisible(not fullscreen)
        self._controls.set_fullscreen(fullscreen)
        if fullscreen:
            self._controls.show_controls()

    def _on_escape(self) -> None:
        if self.window().isFullScreen():
            self._toggle_fullscreen()
        else:
            self._on_back()

    def _on_back(self) -> None:
        self._sidebar.save()
        if self.window().isFullScreen():
            self.window().showNormal()
            self._set_fullscreen_ui(False)
        self.back_requested.emit()

    # — Floating controls positioning —

    def _on_mouse_activity(self) -> None:
        self._controls.show_controls()

    def _on_zoom_changed(self, zoom: float) -> None:
        self._controls.set_zoom(zoom)

    def _reposition_controls(self) -> None:
        """Center controls horizontally at the bottom of the image view."""
        if not hasattr(self, '_controls'):
            return
        self._controls.adjustSize()
        iv = self._image_view
        x = max(0, (iv.width() - self._controls.width()) // 2)
        y = max(0, iv.height() - self._controls.height() - 24)
        self._controls.move(x, y)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self.isVisible():
            self._reposition_controls()