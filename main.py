# entry point: loads ui, ensures database is initialized
import sys
from PySide6.QtWidgets import QApplication # boots windowing system
from ui.main_window import ImageViewerApp # creates main window
from services.db_handler import init_db # ensures sqlite db is ready
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

def main():
    init_db() # initialize database (from db_handler.py)
    app = QApplication(sys.argv) # create app
    window = ImageViewerApp() # load and show the main window (from ui_main.py)
    window.show()

    sys.exit(app.exec()) # makes it appear on screen

if __name__ == "__main__":
    main()