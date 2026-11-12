import sys
import faulthandler                       # <- new
import logging
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImageReader    # <- new
from ui.main_window import ImageViewerApp
from ui.theme import apply_dark_theme
from services.db_handler import init_db

# If the app crashes natively, Python's normal error output never appears.
# faulthandler writes the Python stack at the moment of the crash into crash.log.
_crash_log = open("crash.log", "w")       # keep this reference alive for the whole run
faulthandler.enable(file=_crash_log)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

def main():
    init_db()
    app = QApplication(sys.argv)
    QImageReader.setAllocationLimit(1024)   # MB. Default 256 rejects very large images
    apply_dark_theme(app)
    window = ImageViewerApp()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()