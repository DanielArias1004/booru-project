# ui/browse/browse_widget.py
import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QListView, QAbstractItemView, QLabel, QStackedWidget
)
from PySide6.QtCore import Qt, Signal, QTimer, QSize

from services.config_handler import get_base_folders
from services.image_loader import load_images_from_folder
from ui.browse.image_grid_model import ImageGridModel
from ui.settings_widget import SettingsWidget

THUMB_SIZES = {
    "small":  100,
    "medium": 150,
    "large":  250,
}

# page indices — use these constants everywhere instead of magic numbers
PAGE_BROWSE    = 0
PAGE_FAVORITES = 1
PAGE_ARTISTS   = 2
PAGE_TAGS      = 3
PAGE_POOLS     = 4
PAGE_HELP      = 5
PAGE_SETTINGS  = 6


class BrowseWidget(QWidget):
    image_activated = Signal(list, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thumb_size: int = THUMB_SIZES["medium"]
        self._pending_size: int = self._thumb_size
        self._nav_buttons: dict[str, QPushButton] = {}

        self._resize_timer = QTimer()
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(150)
        self._resize_timer.timeout.connect(self._apply_thumb_size)

        self._visible_timer = QTimer()
        self._visible_timer.setSingleShot(True)
        self._visible_timer.setInterval(50)
        self._visible_timer.timeout.connect(self._load_visible)

        self._model = ImageGridModel()
        self._build_ui()
        self.reload_images()

    # — UI construction —

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_nav_bar())

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_browse_page())   # PAGE_BROWSE
        self._stack.addWidget(self._build_stub_page(       # PAGE_FAVORITES
            "Favorites", "♥",
            "Your favorited images will appear here.\n"
            "Use the ♥ button in the canvas to favorite an image."
        ))
        self._stack.addWidget(self._build_stub_page(       # PAGE_ARTISTS
            "Artists", "🎨",
            "Artists will appear here once you tag images with artist names."
        ))
        self._stack.addWidget(self._build_stub_page(       # PAGE_TAGS
            "Tags", "🏷",
            "All tags will appear here once you start tagging images."
        ))
        self._stack.addWidget(self._build_stub_page(       # PAGE_POOLS
            "Pools", "📁",
            "Pools let you group images into playlists or moods.\nComing soon."
        ))
        self._stack.addWidget(self._build_help_page())     # PAGE_HELP

        self._settings_widget = SettingsWidget()
        self._settings_widget.folders_changed.connect(self.reload_images)
        self._stack.addWidget(self._settings_widget)       # PAGE_SETTINGS

        layout.addWidget(self._stack)
        self._switch_page("Browse")

    def _build_nav_bar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(44)
        bar.setStyleSheet(
            "background: #141414;"
            "border-bottom: 1px solid #2a2a2a;"
        )
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(0)

        title = QLabel("JiBooru")
        title.setStyleSheet(
            "color: #5fa8ff; font-weight: bold;"
            "font-size: 15px; padding-right: 24px;"
        )
        layout.addWidget(title)

        pages = [
            ("Browse",    "🖼"),
            ("Favorites", "♥"),
            ("Artists",   "🎨"),
            ("Tags",      "🏷"),
            ("Pools",     "📁"),
            ("Help",      "❓"),
            ("Settings",  "⚙"),
        ]

        btn_style = """
            QPushButton {
                background: transparent;
                color: #888;
                border: none;
                border-bottom: 3px solid transparent;
                padding: 0 14px;
                font-size: 13px;
                height: 44px;
            }
            QPushButton:checked {
                color: white;
                border-bottom: 3px solid #5fa8ff;
            }
            QPushButton:hover:!checked {
                color: #ddd;
            }
        """

        for name, icon in pages:
            btn = QPushButton(f"{icon}  {name}")
            btn.setCheckable(True)
            btn.setFixedHeight(44)
            btn.setStyleSheet(btn_style)
            btn.clicked.connect(lambda _, n=name: self._switch_page(n))
            self._nav_buttons[name] = btn
            layout.addWidget(btn)

        layout.addStretch()
        return bar

    def _build_browse_page(self) -> QWidget:
        page = QWidget()
        page_layout = QHBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)

        # Left tag sidebar
        from ui.tag_sidebar import TagSidebar
        self._tag_sidebar = TagSidebar()
        self._tag_sidebar.tag_clicked.connect(self._on_tag_filter)
        self._tag_sidebar.search_submitted.connect(self._on_tag_search)
        page_layout.addWidget(self._tag_sidebar)

        # Right: size controls + grid
        right = QWidget()
        layout = QVBoxLayout(right)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # total count label
        self._total_label = QLabel("0 images")
        self._total_label.setStyleSheet("color: #666; font-size: 11px;")

        top_bar = QHBoxLayout()
        for size_name, size_px in THUMB_SIZES.items():
            btn = QPushButton(size_name.capitalize())
            btn.setFixedHeight(28)
            btn.clicked.connect(lambda _, s=size_px: self._set_thumb_size(s))
            top_bar.addWidget(btn)
        top_bar.addStretch()
        top_bar.addWidget(self._total_label)
        layout.addLayout(top_bar)

        # grid
        self._view = QListView()
        self._view.setModel(self._model)
        self._view.setViewMode(QListView.IconMode)
        self._view.setResizeMode(QListView.Adjust)
        self._view.setUniformItemSizes(True)
        self._view.setSpacing(4)
        self._view.setMovement(QListView.Static)
        self._view.setSelectionMode(QAbstractItemView.SingleSelection)
        self._view.setWordWrap(False)
        self._view.setMouseTracking(True)
        self._view.setIconSize(QSize(self._thumb_size, self._thumb_size))
        self._view.setGridSize(QSize(self._thumb_size + 8, self._thumb_size + 8))
        self._view.setStyleSheet("""
            QListView {
                background-color: #111111;
                border: none;
            }
            QListView::item {
                background-color: #1a1a1a;
                border-radius: 2px;
            }
            QListView::item:hover {
                border: 2px solid #5fa8ff;
            }
            QListView::item:selected {
                border: 2px solid #ffffff;
                background-color: #2a2a2a;
            }
        """)
        self._view.clicked.connect(self._on_item_clicked)
        self._view.verticalScrollBar().valueChanged.connect(
            self._visible_timer.start
        )
        layout.addWidget(self._view)
        page_layout.addWidget(right, stretch=1)
        return page

    def _build_stub_page(self, title: str, icon: str, message: str) -> QWidget:
        """Placeholder for features not yet built."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(8)

        icon_lbl = QLabel(icon)
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet("font-size: 52px; margin-bottom: 8px;")
        layout.addWidget(icon_lbl)

        title_lbl = QLabel(title)
        title_lbl.setAlignment(Qt.AlignCenter)
        title_lbl.setStyleSheet(
            "font-size: 20px; font-weight: bold; margin-bottom: 4px;"
        )
        layout.addWidget(title_lbl)

        msg_lbl = QLabel(message)
        msg_lbl.setAlignment(Qt.AlignCenter)
        msg_lbl.setWordWrap(True)
        msg_lbl.setStyleSheet("color: #777; font-size: 13px;")
        layout.addWidget(msg_lbl)
        return page

    def _build_help_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(48, 32, 48, 32)
        layout.setAlignment(Qt.AlignTop)

        title = QLabel("Help")
        title.setStyleSheet(
            "font-size: 22px; font-weight: bold; margin-bottom: 20px;"
        )
        layout.addWidget(title)

        content = QLabel("""
<b>Browse</b><br>
- Click any image to open it in the canvas viewer.<br>
- Use the Small / Medium / Large buttons to change thumbnail size.<br>
- Switch pages using the nav bar at the top.<br>
<br>
<b>Canvas</b><br>
- Scroll wheel to zoom in/out. Drag to pan.<br>
- Double-click the image to reset zoom and pan.<br>
- Left / Right arrow keys (or ⏮ ⏭) to navigate images.<br>
- F11 for fullscreen — Escape to exit.<br>
- Space to play/pause animated GIFs and WebPs.<br>
- , and . to step backward/forward one frame.<br>
- N to hide/show the notes panel.<br>
- Hover over the image to show the floating controls.<br>
- Click 📌 to pin the controls so they stay visible.<br>
<br>
<b>Settings</b><br>
- Add base folders — every image in them appears in the browse grid.<br>
- Remove a base folder to stop showing its images.<br>
        """)
        content.setWordWrap(True)
        content.setStyleSheet(
            "color: #bbb; font-size: 13px; line-height: 1.8;"
        )
        content.setTextFormat(Qt.RichText)
        layout.addWidget(content)
        layout.addStretch()
        return page

    # — Page switching —

    def _switch_page(self, name: str) -> None:
        mapping = {
            "Browse":    PAGE_BROWSE,
            "Favorites": PAGE_FAVORITES,
            "Artists":   PAGE_ARTISTS,
            "Tags":      PAGE_TAGS,
            "Pools":     PAGE_POOLS,
            "Help":      PAGE_HELP,
            "Settings":  PAGE_SETTINGS,
        }
        self._stack.setCurrentIndex(mapping.get(name, PAGE_BROWSE))
        for btn_name, btn in self._nav_buttons.items():
            btn.setChecked(btn_name == name)

    # — Image loading —

    def reload_images(self) -> None:
        paths = []
        for base in get_base_folders():
            if os.path.isdir(base):
                paths.extend(load_images_from_folder(base, base))
        paths.sort()
        self._model.set_paths(paths)
        if hasattr(self, '_total_label'):
            self._total_label.setText(f"{len(paths)} images")
        if hasattr(self, '_tag_sidebar'):
            self._tag_sidebar.refresh()
        QTimer.singleShot(200, self._load_visible)

    def _on_item_clicked(self, index) -> None:
        self.image_activated.emit(self._model.all_paths(), index.row())

    def _set_thumb_size(self, size: int) -> None:
        self._pending_size = size
        self._resize_timer.start()

    def _apply_thumb_size(self) -> None:
        if self._pending_size == self._thumb_size:
            return
        self._thumb_size = self._pending_size
        self._model.set_thumb_size(self._thumb_size)
        self._view.setIconSize(QSize(self._thumb_size, self._thumb_size))
        self._view.setGridSize(QSize(self._thumb_size + 8, self._thumb_size + 8))
        QTimer.singleShot(50, self._load_visible)

    def _load_visible(self) -> None:
        if self._model.rowCount() == 0:
            return

        vp_rect = self._view.viewport().rect()
        top_index = self._view.indexAt(vp_rect.topLeft())

        if not top_index.isValid():
            # view hasn't laid out yet — retry in 100ms
            QTimer.singleShot(100, self._load_visible)
            return

        bottom_index = self._view.indexAt(vp_rect.bottomRight())
        first = top_index.row()
        last = (
            bottom_index.row()
            if bottom_index.isValid()
            else min(self._model.rowCount() - 1, first + 50)
        )

        self._model.prioritize_visible(first, last)

        # load visible items + one screen of buffer above and below
        buffer = max(20, last - first + 1)
        load_first = max(0, first - buffer)
        load_last = min(self._model.rowCount() - 1, last + buffer)

        for row in range(load_first, load_last + 1):
            self._model.request_thumbnail(row)

    def _on_tag_filter(self, tag_name: str) -> None:
        """Filter grid to images matching all active tags."""
        active = self._tag_sidebar.get_active_tags()
        if not active:
            self.reload_images()
            return
        from services.db_handler import search_images_by_tags, get_base_folders
        import os
        # search_images_by_tags returns relative paths — resolve to absolute
        bases = get_base_folders()
        rel_paths = search_images_by_tags(active)
        abs_paths = []
        for rel in rel_paths:
            for base in bases:
                candidate = os.path.normpath(os.path.join(base, rel))
                if os.path.exists(candidate):
                    abs_paths.append(candidate)
                    break
        abs_paths.sort()
        self._model.set_paths(abs_paths)
        self._total_label.setText(f"{len(abs_paths)} images")
        QTimer.singleShot(200, self._load_visible)

    def _on_tag_search(self, query: str) -> None:
        """Search by space-separated tag names."""
        if not query:
            self.reload_images()
            return
        tags = query.split()
        self._on_tag_filter_list(tags)