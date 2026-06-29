# viewer/main_window.py
import os

from PySide6.QtWidgets import QMainWindow, QTabWidget

from services.db_handler import get_folders
from services.image_loader import load_images_from_folder
from services.config_handler import get_base_folder
from ui.canvas.canvas import CanvasMixin
from ui.folders.folders import FoldersMixin


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

    def on_tab_changed(self, idx: int) -> None:
        if self.tabs.tabText(idx) == "Canvas":
            self.load_all_images()

    def load_all_images(self) -> None:
        """Collect all images from saved folders and display the first one."""
        if not self.base_folder:
            return
        paths = []
        for rel in get_folders():
            abs_path = os.path.join(self.base_folder, rel)
            if os.path.isdir(abs_path):
                paths.extend(load_images_from_folder(abs_path))
        self.image_paths = sorted(paths)
        self.current_index = 0
        self.show_image()