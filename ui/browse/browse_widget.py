# ui/browse/browse_widget.py
import os

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QStackedWidget, QCheckBox, QSplitter
)
from PySide6.QtCore import Qt, Signal, QTimer

from services.config_handler import get_base_folders
from services.image_loader import load_images_from_folder
from ui.browse.image_grid import ImageGrid
from ui.browse.folder_tree import FolderTree
from ui.browse.favorites_page import FavoritesPage
from ui.browse.pools_page import PoolsPage
from ui.settings_widget import SettingsWidget

# Order here must match the order pages are added to the stack in _build_ui
PAGES = [("Browse", "🖼"), ("Favorites", "♥"), ("Pools", "📁"),
         ("Help", "❓"), ("Settings", "⚙")]


class BrowseWidget(QWidget):
    image_activated = Signal(list, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._nav_buttons: dict[str, QPushButton] = {}
        self._current_folder: str | None = None
        self._build_ui()
        QTimer.singleShot(0, self.reload_images)   # let the window appear first

    # — UI construction —

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_nav_bar())

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_browse_page())      # Browse

        self._favorites = FavoritesPage()                     # Favorites
        self._favorites.image_activated.connect(self.image_activated)
        self._stack.addWidget(self._favorites)

        self._pools = PoolsPage()                             # Pools
        self._pools.image_activated.connect(self.image_activated)
        self._stack.addWidget(self._pools)

        self._stack.addWidget(self._build_help_page())        # Help

        self._settings_widget = SettingsWidget()              # Settings
        self._settings_widget.folders_changed.connect(self.reload_images)
        self._stack.addWidget(self._settings_widget)

        layout.addWidget(self._stack)
        self._switch_page("Browse")

    def _build_nav_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("navBar")
        bar.setFixedHeight(44)
        # "#navBar { ... }" only styles THIS widget, not its children
        bar.setStyleSheet("#navBar { background: #141414; border-bottom: 1px solid #2a2a2a; }")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(0)

        title = QLabel("JiBooru")
        title.setStyleSheet("color: #5fa8ff; font-weight: bold; font-size: 15px; padding-right: 24px;")
        layout.addWidget(title)

        btn_style = """
            QPushButton { background: transparent; color: #aaa; border: none;
                          border-bottom: 3px solid transparent; padding: 0 14px;
                          font-size: 13px; height: 44px; }
            QPushButton:checked { color: white; border-bottom: 3px solid #5fa8ff; }
            QPushButton:hover:!checked { color: #ddd; }
        """
        for name, icon in PAGES:
            btn = QPushButton(f"{icon}  {name}")
            btn.setCheckable(True)
            btn.setFixedHeight(44)
            btn.setStyleSheet(btn_style)
            btn.clicked.connect(lambda _checked=False, n=name: self._switch_page(n))
            self._nav_buttons[name] = btn
            layout.addWidget(btn)
        layout.addStretch()
        return bar

    def _build_browse_page(self) -> QWidget:
        splitter = QSplitter(Qt.Horizontal)

        self._folder_tree = FolderTree()
        self._folder_tree.folder_selected.connect(self._on_folder_selected)
        splitter.addWidget(self._folder_tree)

        self._grid = ImageGrid()
        self._grid.image_activated.connect(self.image_activated)
        self._subfolders_cb = QCheckBox("Include subfolders")
        self._subfolders_cb.toggled.connect(lambda _checked: self._reload_current_folder())
        self._grid.add_toolbar_widget(self._subfolders_cb)
        splitter.addWidget(self._grid)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([240, 960])
        return splitter

    def _build_help_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(48, 32, 48, 32)
        layout.setAlignment(Qt.AlignTop)

        title = QLabel("Help")
        title.setStyleSheet("font-size: 22px; font-weight: bold; margin-bottom: 20px;")
        layout.addWidget(title)

        content = QLabel("""
<b>Browse</b><br>
- Pick a folder on the left to see its images. Tick "Include subfolders" to see everything below it.<br>
- Click an image to open it. Right-click is available on Favorites and Pools.<br>
<br>
<b>Viewer</b><br>
- Scroll wheel to zoom, drag to pan, double-click to reset.<br>
- Left / Right arrows to navigate. F11 fullscreen, Escape to exit.<br>
- Space plays/pauses GIFs. , and . step frames. N hides the sidebar.<br>
- ♡ Favorite and ＋ Pool are at the top of the sidebar.<br>
<br>
<b>Pools</b><br>
- Create pools on the Pools page, add images from the viewer's ＋ Pool button.<br>
<br>
<b>Settings</b><br>
- Add base folders; they show up as roots of the folder tree.<br>
        """)
        content.setWordWrap(True)
        content.setTextFormat(Qt.RichText)
        content.setStyleSheet("color: #ccc; font-size: 13px;")
        layout.addWidget(content)
        layout.addStretch()
        return page

    # — Navigation —

    def _switch_page(self, name: str) -> None:
        names = [n for n, _ in PAGES]
        self._stack.setCurrentIndex(names.index(name))
        for btn_name, btn in self._nav_buttons.items():
            btn.setChecked(btn_name == name)

    # — Folder browsing —

    def reload_images(self) -> None:
        """Rebuild the folder tree from the configured base folders."""
        self._folder_tree.reload(get_base_folders())
        if not get_base_folders():
            self._grid.set_paths([])

    def _on_folder_selected(self, path: str) -> None:
        self._current_folder = path
        self._reload_current_folder()

    def _reload_current_folder(self) -> None:
        folder = self._current_folder
        if not folder or not os.path.isdir(folder):
            self._grid.set_paths([])
            return
        paths = load_images_from_folder(folder, recursive=self._subfolders_cb.isChecked())
        self._grid.set_paths(paths)