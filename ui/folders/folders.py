# viewer/folders.py
import os
from turtle import left

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QListWidget, QFileDialog, QSizePolicy, QTreeView, QMessageBox
)
from PySide6.QtWidgets import QFileSystemModel

from services.image_loader import load_images_from_folder
from services.config_handler import get_base_folders, add_base_folder, remove_base_folder
from services.db_handler import add_folder, remove_folder, get_folders


class FoldersMixin:
    """Provides the Folders tab UI and all folder/tree navigation logic."""

    def build_folders_tab(self) -> QWidget:
        """Folders: saved-folders list + Add/Remove on left, file tree on right."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Base folder management bar
        base_bar = QHBoxLayout()
        add_base_btn = QPushButton("+ Add Base Folder")
        add_base_btn.clicked.connect(self.prompt_add_base_folder)
        base_bar.addWidget(add_base_btn)
        base_bar.addStretch()
        layout.addLayout(base_bar)

        # base folders list (shows all base folders with remove buttons)
        self.base_folder_list = QWidget()
        self.base_folder_list_layout = QVBoxLayout(self.base_folder_list)
        self.base_folder_list_layout.setContentsMargins(0, 0, 0, 0)
        self.base_folder_list_layout.setSpacing(2)
        layout.addWidget(self.base_folder_list)

        # Breadcrumb path bar
        self.breadcrumb_bar = QHBoxLayout()
        self.breadcrumb_bar.setSpacing(5)
        layout.addLayout(self.breadcrumb_bar)

        change_btn = QPushButton("Change Base Folder")
        change_btn.clicked.connect(self.prompt_add_base_folder)
        layout.addWidget(change_btn)

        # Content: left panel (staged folders) + right panel (file tree)
        content_layout = QHBoxLayout()

        # Left: add/remove buttons + saved folder list
        left = QVBoxLayout()
        btn_row = QHBoxLayout()
        add_btn = QPushButton("+ Stage")
        add_btn.setToolTip("Stage selected folder")
        add_btn.clicked.connect(self._ui_add_folder)
        btn_row.addWidget(add_btn)
        btn_row.addStretch()
        left.addLayout(btn_row)

        self.folder_list = QListWidget()
        left.addWidget(self.folder_list)

        # Right: file system tree
        self.fs_model = QFileSystemModel()
        self.fs_model.setNameFilters(["*.jpg", "*.jpeg", "*.png", "*.webp", "*.bmp", "*.gif"])
        self.fs_model.setNameFilterDisables(False)

        self.tree = QTreeView()
        self.tree.doubleClicked.connect(self._on_file_double_clicked)

        content_layout.addLayout(left, 1)
        content_layout.addWidget(self.tree, 3)
        layout.addLayout(content_layout)

        return tab

    # — Folder list management —

    def _ui_add_folder(self) -> None:
        index = self.tree.currentIndex()
        if not index.isValid():
            QMessageBox.warning(self, "No folder selected", "Please select a folder in the tree.")
            return

        abs_path = self.fs_model.filePath(index)
        if not os.path.isdir(abs_path):
            QMessageBox.warning(self, "Invalid selection", "Please select a folder, not a file.")
            return

        # figure out which base folder this path belongs to
        base = self._get_base_folder_for_path(abs_path)
        if not base:
            QMessageBox.warning(self, "Outside base folders",
                "Selected folder is not inside any of your base folders.")
            return

        rel = os.path.relpath(abs_path, base)
        existing = [(b, p) for b, p in get_folders() if b == base and p == rel]
        if existing:
            QMessageBox.information(self, "Already staged", "This folder is already staged.")
            return

        add_folder(base, rel)
        self.refresh_folders() # refresh since the staged folder list has changed
        self.load_all_images()

    def refresh_folders(self) -> None:
        """Rebuild the staged folders list with inline remove buttons."""
        self.folder_list.clear()
        for base, rel in get_folders():
            self.folder_list.addItem(f"[{os.path.basename(base)}] {rel}")

    def refresh_base_folders(self) -> None:
        """Rebuild the base folders display with remove buttons."""
        for i in reversed(range(self.base_folder_list_layout.count())):
            w = self.base_folder_list_layout.itemAt(i).widget()
            if w:
                w.setParent(None)

        for base in self.base_folders:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)

            label = QLabel(base)
            label.setStyleSheet("font-weight: bold; padding: 2px 4px;")
            row_layout.addWidget(label, stretch=1)

            rem_btn = QPushButton("✕")
            rem_btn.setFixedSize(24, 24)
            rem_btn.setToolTip("Remove this base folder")
            rem_btn.clicked.connect(lambda _checked, b=base: self._remove_base_folder(b))
            row_layout.addWidget(rem_btn)

            self.base_folder_list_layout.addWidget(row)

    def prompt_add_base_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Add Base Folder")
        if not folder:
            return
        add_base_folder(folder)
        self.base_folders = get_base_folders()
        self.refresh_base_folders()
        self._init_tree()
        self.refresh_folders()
        self.load_all_images()

    def _remove_base_folder(self, base: str) -> None:
        remove_base_folder(base)
        self.base_folders = get_base_folders()
        self.refresh_base_folders()
        self.refresh_folders()
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