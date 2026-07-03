# viewer/main_window.py
import os

from PySide6.QtWidgets import QMainWindow, QStackedWidget
from PySide6.QtGui import QShortcut, QKeySequence

from ui.browse.browse_widget import BrowseWidget
from ui.canvas.canvas_widget import CanvasWidget
from services.config_handler import get_base_folders


class ImageViewerApp(QMainWindow):
    """
    Main application window.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("JiBooru")
        self.resize(1200, 800)

        # QStackedWidget holds our two pages
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        # Create the two pages
        self.browse = BrowseWidget()
        self.canvas = CanvasWidget()

        self.stack.addWidget(self.browse) # index 0
        self.stack.addWidget(self.canvas) # index 1

        # Wire: clicking an image in browse will open it in canvas
        self.browse.image_activated.connect(self._open_in_canvas) # signal from BrowseWidget to open the image in CanvasWidget

        # Wire: pressing back in canvas will return to browse
        self.canvas.back_requested.connect(self._go_to_browse) # signal from CanvasWidget to return to BrowseWidget

        # Start on browsewidget when you open the app
        self.stack.setCurrentIndex(0)

    def _open_in_canvas(self, image_paths: list[str], index: int) -> None:
        """Switch to canvas and show the selected image."""
        self.canvas.load(image_paths, index)
        self.stack.setCurrentIndex(1)

    def _go_to_browse(self) -> None:
        """Switch to browse."""
        self.stack.setCurrentIndex(0)