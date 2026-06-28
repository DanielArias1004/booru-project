import sys
import os
import random
import sqlite3
from datetime import datetime
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTextEdit, QTabWidget, QTreeView,
    QFileSystemModel, QListWidget, QFileDialog, QScrollArea, QSizePolicy,
    QMessageBox
)
from PySide6.QtGui import QPixmap, QIcon
from PySide6.QtCore import Qt, QSize
from viewer.db_handler import (
    add_folder, get_folders, get_latest_note, add_note, DB_PATH
)
from viewer.image_loader import load_images_from_folder
from viewer.config_handler import get_base_folder, set_base_folder

class ImageViewerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Image Viewer")
        self.resize(1200, 800)

        # State
        self.image_paths = []
        self.current_index = 0
        self.base_folder = get_base_folder() # Load saved base folder from config.json
        if not self.base_folder or not os.path.exists(self.base_folder):
            self.prompt_for_base_folder() # No valid folder saved → prompt now

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.addTab(self.build_canvas_tab(), "Canvas")
        self.tabs.addTab(self.build_folders_tab(), "Folders")
        self.setCentralWidget(self.tabs)
        self.tabs.currentChanged.connect(self.on_tab_changed)

        # Now that 'self.tree' and 'self.fs_model' exist, load or prompt for base folder
        self.base_folder = get_base_folder()
        if not self.base_folder or not os.path.exists(self.base_folder):
            self.prompt_for_base_folder()
        else:
            # If a valid base folder was found, explicitly set up the tree immediately
            self.fs_model.setRootPath(self.base_folder)
            self.tree.setModel(self.fs_model)
            self.tree.setRootIndex(self.fs_model.index(self.base_folder))
            self.refresh_folders()

    def build_canvas_tab(self):
        """Canvas: image & notes side-by-side, scrollable carousel, nav buttons."""
        tab = QWidget()
        v = QVBoxLayout(tab)

        # Top: image + notes
        top = QHBoxLayout()
        self.image_label = QLabel("No image loaded")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("background-color:#111;")
        self.image_label.setMinimumSize(600,400)
        top.addWidget(self.image_label, 3)

        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("Enter notes here…")
        self.notes_edit.setStyleSheet("background-color:#222; color:white;")
        self.notes_edit.setFixedWidth(250)
        top.addWidget(self.notes_edit, 1)
       
        v.addLayout(top)

        # Carousel inside a scroll area
        self.carousel_container = QWidget()
        self.carousel_layout = QHBoxLayout(self.carousel_container)
        self.carousel_layout.setSpacing(5)
        self.carousel_layout.setContentsMargins(0,0,0,0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(self.carousel_container)
        scroll.setFixedHeight(120)
        v.addWidget(scroll)

        # Nav buttons
        nav = QHBoxLayout()
        self.prev_btn = QPushButton("⏮")
        self.prev_btn.clicked.connect(self.show_previous)
        self.shuffle_btn = QPushButton("🔀")
        self.shuffle_btn.clicked.connect(self.show_random)
        self.next_btn = QPushButton("⏭")
        self.next_btn.clicked.connect(self.show_next)
        for btn in (self.prev_btn, self.shuffle_btn, self.next_btn):
            btn.setFixedSize(40,40)
            nav.addWidget(btn)
        nav.addSpacing(10) # spacing between the buttons and label

        # add index and filename label here
        self.index_label = QLabel("No images loaded")
        self.index_label.setStyleSheet("font-weight: bold;")
        nav.addWidget(self.index_label)

        nav.addStretch()
        v.addLayout(nav)

        return tab

    def build_folders_tab(self):
        """Folders: saved-folders list + Add/Remove on left, file tree on right."""
        tab = QWidget()
        self.folder_tab_layout = QVBoxLayout(tab)

        # Breadcrumb path bar
        self.breadcrumb_bar = QHBoxLayout()
        self.breadcrumb_bar.setSpacing(5)
        self.folder_tab_layout.addLayout(self.breadcrumb_bar)

        # change base folder button
        change_btn = QPushButton("Change Base Folder")
        change_btn.clicked.connect(self.prompt_for_base_folder)
        self.folder_tab_layout.addWidget(change_btn)

        # Left: saved folders
        content_layout = QHBoxLayout()
        left = QVBoxLayout()
        btns = QHBoxLayout()
        add_btn = QPushButton("+")
        add_btn.clicked.connect(self.ui_add_folder)
        rem_btn = QPushButton("–")
        rem_btn.clicked.connect(self.ui_remove_folder)
        btns.addWidget(add_btn)
        btns.addWidget(rem_btn)
        left.addLayout(btns)

        self.folder_list = QListWidget()
        self.folder_list.itemClicked.connect(self.on_folder_selected)
        left.addWidget(self.folder_list)
        self.refresh_folders()

        # Right: file system browser
        self.fs_model = QFileSystemModel()
        self.fs_model.setNameFilters(["*.jpg","*.jpeg","*.png","*.bmp","*.gif"])
        self.fs_model.setNameFilterDisables(False)

        self.tree = QTreeView()
        self.tree.doubleClicked.connect(self.on_file_double_clicked)
        content_layout.addLayout(left, 1)
        content_layout.addWidget(self.tree, 3)

        self.folder_tab_layout.addLayout(content_layout)
        return tab



    # — UI Folder Management —
    def ui_add_folder(self):
        index = self.tree.currentIndex()
        if not index.isValid():
            QMessageBox.warning(self, "No folder selected", "Please select a folder in the trree view.")
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

    def ui_remove_folder(self):
        item = self.folder_list.currentItem()
        if item:
            rel = item.text()
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("DELETE FROM folders WHERE path=?", (rel,))
            conn.commit()
            conn.close()
            self.refresh_folders()

    def refresh_folders(self):
        self.folder_list.clear()
        for f in get_folders():
            self.folder_list.addItem(f)

    def prompt_for_base_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose Base Folder")
        if folder:
            # save and use the new base folder
            self.base_folder = folder
            set_base_folder(folder)

            # reinitialize the file system model and tree
            self.fs_model.setRootPath(self.base_folder)
            self.tree.setModel(self.fs_model)
            self.tree.setRootIndex(self.fs_model.index(self.base_folder))

            # refresh saved folders list (since they may have had a different base folder)
            self.refresh_folders()

            # If currently on Canvas, reload images
            if self.tabs.tabText(self.tabs.currentIndex()) == "Canvas":
                self.load_all_images()
    
    def on_folder_selected(self, item):
        rel = item.text()
        if not self.base_folder:
            QMessageBox.warning(self, "Base Folder Not Set", "Please set the base folder first.")
            return
        abs_path = os.path.normpath(os.path.join(self.base_folder, rel))
        self.set_tree_root(abs_path)

    def on_file_double_clicked(self, idx):
        path = self.fs_model.filePath(idx)
        if os.path.isfile(path):
            folder = os.path.dirname(path)
            imgs = load_images_from_folder(folder)
            imgs.sort()
            self.image_paths = imgs
            self.current_index = imgs.index(path)
            self.show_image()
            self.set_tree_root(folder)

    def update_breadcrumb_bar(self, abs_path):
        # Clear old widgets
        for i in reversed(range(self.breadcrumb_bar.count())):
            widget = self.breadcrumb_bar.itemAt(i).widget()
            if widget:
                widget.setParent(None)

        # Get relative path from base
        rel_path = os.path.relpath(abs_path, self.base_folder)
        parts = rel_path.split(os.sep) if rel_path != "." else []

        # Start with base folder name as root
        home_btn = QPushButton(os.path.basename(self.base_folder))
        home_btn.setStyleSheet("padding: 4px;")
        home_btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        home_btn.clicked.connect(lambda: self.set_tree_root(self.base_folder))
        self.breadcrumb_bar.addWidget(home_btn)

        # Add each folder part as a button
        for i, part in enumerate(parts):
            sep = QLabel(">")
            sep.setStyleSheet("margin: 0 6px; color: gray;")
            self.breadcrumb_bar.addWidget(sep)

            full_path = os.path.join(self.base_folder, *parts[:i+1])
            btn = QPushButton(part)
            btn.setStyleSheet("padding: 4px;")
            btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
            btn.clicked.connect(lambda _checked, p=full_path: self.set_tree_root(p))
            self.breadcrumb_bar.addWidget(btn)

    def set_tree_root(self, abs_path):
        if os.path.isdir(abs_path):
            self.fs_model.setRootPath(abs_path)
            self.tree.setRootIndex(self.fs_model.index(abs_path))
            self.update_breadcrumb_bar(abs_path)



    # — Tab change & image loading —
    def on_tab_changed(self, idx):
        if self.tabs.tabText(idx) == "Canvas":
            self.load_all_images()

    def load_all_images(self):
        """Collect all image paths from saved folders (fast) and sort."""
        if not self.base_folder:
            return
        self.image_paths = []
        for rel in get_folders():
            abs_path = os.path.join(self.base_folder, rel)
            if os.path.isdir(abs_path):
                imgs = load_images_from_folder(abs_path)
                self.image_paths.extend(imgs)
        self.image_paths.sort()
        self.current_index = 0
        self.show_image()

    # — Image display & navigation —
    def show_image(self):
        if not self.image_paths:
            self.index_label.setText("No images loaded")
            self.image_label.setText("No image loaded")
            self.notes_edit.clear()
            self.update_carousel()
            return
        path = self.image_paths[self.current_index]
        pix = QPixmap(path).scaled(
            self.image_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        self.image_label.setPixmap(pix)
        note = get_latest_note(self.get_current_image_id()) or ""
        self.notes_edit.setText(note)

        filename = os.path.basename(path)
        self.index_label.setText(f"Image {self.current_index + 1} of {len(self.image_paths)} — {filename}")

        self.update_carousel()

    def clear_canvas(self):
        self.image_label.clear()
        self.notes_edit.clear()
        for i in reversed(range(self.carousel_layout.count())):
            w = self.carousel_layout.itemAt(i).widget()
            if w:
                w.setParent(None)

    def update_carousel(self):
        """Rebuild thumbnails around current index; clickable to jump."""
        # clear old
        for i in reversed(range(self.carousel_layout.count())):
            w = self.carousel_layout.itemAt(i).widget()
            if w:
                w.setParent(None)

        start = max(0, self.current_index - 2)
        end   = min(len(self.image_paths), self.current_index + 3)
        for idx in range(start, end):
            btn = QPushButton()
            btn.setIcon(QIcon(self.image_paths[idx]))
            btn.setIconSize(QSize(80,80))
            btn.setFixedSize(84,84)
            btn.clicked.connect(lambda _checked, i=idx: self.on_thumb_clicked(i))
            self.carousel_layout.addWidget(btn)

    def on_thumb_clicked(self, idx):
        """Jump to the selected thumbnail index."""
        self.save_current_note()
        self.current_index = idx
        self.show_image()

    def show_previous(self):
        self.save_current_note()
        if self.image_paths:
            self.current_index = (self.current_index - 1) % len(self.image_paths)
            self.show_image()

    def show_next(self):
        self.save_current_note()
        if self.image_paths:
            self.current_index = (self.current_index + 1) % len(self.image_paths)
            self.show_image()

    def show_random(self):
        self.save_current_note()
        if self.image_paths:
            self.current_index = random.randrange(len(self.image_paths))
            self.show_image()

    def save_current_note(self):
        img_id = self.get_current_image_id()
        if img_id:
            add_note(img_id, self.notes_edit.toPlainText(), datetime.now().isoformat())

    def get_current_image_id(self):
        if not self.image_paths:
            return None
        path = self.image_paths[self.current_index]
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT id FROM images WHERE file_path=?", (path,))
        row = cur.fetchone()
        conn.close()
        return row[0] if row else None

    def select_base_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Select Base Folder")
        if path:
            self.base_folder = path
            set_base_folder(path)
            self.fs_model.setRootPath(path)
            self.refresh_folders()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    viewer = ImageViewerApp()
    viewer.show()
    sys.exit(app.exec())
