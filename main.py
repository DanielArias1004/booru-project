# entry point: loads ui, ensures database is initialized
import sys
from PySide6.QtWidgets import QApplication # boots windowing system
from ui.ui_main import ImageViewerApp # creates main window
from services.db_handler import init_db # ensures sqlite db is ready

def main():
    init_db() # initialize database (from db_handler.py)
    app = QApplication(sys.argv) # create app
    window = ImageViewerApp() # load and show the main window (from ui_main.py)
    window.show()

    sys.exit(app.exec()) # makes it appear on screen

if __name__ == "__main__":
    main()