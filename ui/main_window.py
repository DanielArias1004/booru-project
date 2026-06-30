# viewer/main_window.py
import os

from PySide6.QtWidgets import QMainWindow, QTabWidget

from services.db_handler import get_folders
from services.image_loader import load_images_from_folder
from services.config_handler import get_base_folder
from ui.canvas.canvas import CanvasMixin
from ui.folders.folders import FoldersMixin
from PySide6.QtGui import QShortcut, QKeySequence


class ImageViewerApp(CanvasMixin, FoldersMixin, QMainWindow):
    """
    Main application window.

    Inherits UI sections and logic from CanvasMixin and FoldersMixin.
    QMainWindow must be last in the MRO so super() chains work correctly.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Image Viewer")
        self.resize(1200, 800)

        self.image_paths: list[str] = []
        self.current_index: int = 0
        self.base_folder: str = ""

        # Build tabs (this creates self.tree, self.fs_model, etc.)
        self.tabs = QTabWidget()
        self.tabs.addTab(self.build_canvas_tab(), "Canvas")
        self.tabs.addTab(self.build_folders_tab(), "Folders")
        self.setCentralWidget(self.tabs)
        self.tabs.currentChanged.connect(self.on_tab_changed)

        # Now safe to use self.tree / self.fs_model
        self.base_folder = get_base_folder()
        if not self.base_folder or not os.path.exists(self.base_folder):
            self.prompt_for_base_folder()
        else:
            self.fs_model.setRootPath(self.base_folder)
            self.tree.setModel(self.fs_model)
            self.tree.setRootIndex(self.fs_model.index(self.base_folder))
            self.refresh_folders()

        self.load_all_images() # load all images on app load

        # keyboard shortcuts for navigation
        QShortcut(QKeySequence("Left"), self, self.show_previous)
        QShortcut(QKeySequence("Right"), self, self.show_next)
        QShortcut(QKeySequence("R"), self, self.show_random) # R might not work


    def on_tab_changed(self, idx: int) -> None:
        if self.tabs.tabText(idx) == "Canvas": # fragile, may need to make constants like TAB_CANVAS = 0 and use that. if the tab name changes, it will break.
            self.load_all_images()

    # this needs to not load all images at once or 
    def load_all_images(self) -> None:
        """Collect all images from staged folders and display the first one."""
        if not self.base_folder:
            return
        paths = []
        for rel in get_folders(): # gets the relative paths of the folders from the DB
            abs_path = os.path.join(self.base_folder, rel) # creates an absolute path by joining the base folder with the relative path
            if os.path.isdir(abs_path): # if the absolute path is a directory, load images from it
                paths.extend(load_images_from_folder(abs_path, self.base_folder)) 
        self.image_paths = sorted(paths)
        self.current_index = 0
        self.show_image()