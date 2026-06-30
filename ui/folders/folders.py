# viewer/folders.py
import os

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QListWidget, QFileDialog, QSizePolicy, QTreeView, QMessageBox
)
from PySide6.QtWidgets import QFileSystemModel

from services.db_handler import add_folder, get_folders, remove_folder
from services.config_handler import set_base_folder
from services.image_loader import load_images_from_folder


class FoldersMixin:
    """Provides the Folders tab UI and all folder/tree navigation logic."""

    def build_folders_tab(self) -> QWidget:
        """Folders: saved-folders list + Add/Remove on left, file tree on right."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Breadcrumb path bar
        self.breadcrumb_bar = QHBoxLayout()
        self.breadcrumb_bar.setSpacing(5)
        layout.addLayout(self.breadcrumb_bar)

        change_btn = QPushButton("Change Base Folder")
        change_btn.clicked.connect(self.prompt_for_base_folder)
        layout.addWidget(change_btn)

        # Content: left panel (saved folders) + right panel (file tree)
        content_layout = QHBoxLayout()

        # Left: add/remove buttons + saved folder list
        left = QVBoxLayout()
        btn_row = QHBoxLayout()
        add_btn = QPushButton("+")
        add_btn.setToolTip("Save selected folder to your list")
        add_btn.clicked.connect(self._ui_add_folder)
        rem_btn = QPushButton("–")
        rem_btn.setToolTip("Remove selected folder from your list")
        rem_btn.clicked.connect(self._ui_remove_folder)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(rem_btn)
        left.addLayout(btn_row)

        self.folder_list = QListWidget()
        self.folder_list.itemClicked.connect(self._on_folder_selected)
        left.addWidget(self.folder_list)

        # Right: file system tree
        self.fs_model = QFileSystemModel()
        self.fs_model.setNameFilters(["*.jpg", "*.jpeg", "*.png", "*.bmp", "*.gif"])
        self.fs_model.setNameFilterDisables(False)

        self.tree = QTreeView()
        self.tree.doubleClicked.connect(self._on_file_double_clicked)

        content_layout.addLayout(left, stretch=1)
        content_layout.addWidget(self.tree, stretch=3)
        layout.addLayout(content_layout)

        return tab

    # — Folder list management —

    def _ui_add_folder(self) -> None:
        """Save the currently selected tree folder to the DB."""
        index = self.tree.currentIndex()
        if not index.isValid():
            QMessageBox.warning(self, "No folder selected", "Please select a folder in the tree view.")
            return

        abs_path = self.fs_model.filePath(index)
        if not os.path.isdir(abs_path):
            QMessageBox.warning(self, "Invalid selection", "Please select a folder, not a file.")
            return

        rel = os.path.relpath(abs_path, self.base_folder)
        if rel in get_folders():
            QMessageBox.information(self, "Already added", "This folder is already in your list.")
            return

        add_folder(rel)
        self.refresh_folders()

    def _ui_remove_folder(self) -> None:
        """Remove the currently selected saved folder from the DB."""
        item = self.folder_list.currentItem()
        if item:
            remove_folder(item.text())
            self.refresh_folders()

    def refresh_folders(self) -> None:
        """Reload the saved folders list from the DB."""
        self.folder_list.clear()
        for path in get_folders():
            self.folder_list.addItem(path)

    def prompt_for_base_folder(self) -> None:
        """Open a dialog to pick a new base folder, then update all state."""
        folder = QFileDialog.getExistingDirectory(self, "Choose Base Folder")
        if not folder:
            return  # user cancelled

        self.base_folder = folder
        set_base_folder(folder)

        self.fs_model.setRootPath(self.base_folder)
        self.tree.setModel(self.fs_model)
        self.tree.setRootIndex(self.fs_model.index(self.base_folder))
        self.refresh_folders()

        if self.tabs.tabText(self.tabs.currentIndex()) == "Canvas":
            self.load_all_images()

    # — Tree navigation —

    def _on_folder_selected(self, item) -> None:
        """Navigate the file tree to the clicked saved folder."""
        if not self.base_folder:
            QMessageBox.warning(self, "Base Folder Not Set", "Please set the base folder first.")
            return
        abs_path = os.path.normpath(os.path.join(self.base_folder, item.text()))
        self.set_tree_root(abs_path)

    def _on_file_double_clicked(self, idx) -> None:
        """Load all images from the folder containing the double-clicked file."""
        path = self.fs_model.filePath(idx)
        if not os.path.isfile(path):
            return
        folder = os.path.dirname(path)
        imgs = sorted(load_images_from_folder(folder, self.base_folder))
        if path not in imgs:
            return
        self.image_paths = imgs
        self.current_index = imgs.index(path)
        self.show_image()
        self.set_tree_root(folder)

    def set_tree_root(self, abs_path: str) -> None:
        """Point the file tree at the given folder and update the breadcrumb."""
        if os.path.isdir(abs_path):
            self.fs_model.setRootPath(abs_path)
            self.tree.setRootIndex(self.fs_model.index(abs_path))
            self._update_breadcrumb(abs_path)

    def _update_breadcrumb(self, abs_path: str) -> None:
        """Rebuild the clickable breadcrumb bar for the given path."""
        # Remove old widgets
        for i in reversed(range(self.breadcrumb_bar.count())):
            widget = self.breadcrumb_bar.itemAt(i).widget()
            if widget:
                widget.setParent(None)

        rel_path = os.path.relpath(abs_path, self.base_folder)
        parts = rel_path.split(os.sep) if rel_path != "." else []

        home_btn = QPushButton(os.path.basename(self.base_folder))
        home_btn.setStyleSheet("padding: 4px;")
        home_btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        home_btn.clicked.connect(lambda: self.set_tree_root(self.base_folder))
        self.breadcrumb_bar.addWidget(home_btn)

        for i, part in enumerate(parts):
            sep = QLabel(">")
            sep.setStyleSheet("margin: 0 6px; color: gray;")
            self.breadcrumb_bar.addWidget(sep)

            full_path = os.path.join(self.base_folder, *parts[: i + 1])
            btn = QPushButton(part)
            btn.setStyleSheet("padding: 4px;")
            btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
            btn.clicked.connect(lambda _checked, p=full_path: self.set_tree_root(p))
            self.breadcrumb_bar.addWidget(btn)