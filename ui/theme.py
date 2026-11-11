# ui/theme.py
from PySide6.QtGui import QPalette, QColor


def apply_dark_theme(app) -> None:
    """Fusion style + a dark palette, so every widget has readable defaults."""
    app.setStyle("Fusion")
    p = QPalette()
    c = QColor
    p.setColor(QPalette.Window, c("#1a1a1a"))
    p.setColor(QPalette.WindowText, c("#dddddd"))
    p.setColor(QPalette.Base, c("#111111"))
    p.setColor(QPalette.AlternateBase, c("#1e1e1e"))
    p.setColor(QPalette.Text, c("#dddddd"))
    p.setColor(QPalette.Button, c("#2a2a2a"))
    p.setColor(QPalette.ButtonText, c("#dddddd"))
    p.setColor(QPalette.ToolTipBase, c("#2a2a2a"))
    p.setColor(QPalette.ToolTipText, c("#dddddd"))
    p.setColor(QPalette.PlaceholderText, c("#888888"))
    p.setColor(QPalette.Highlight, c("#5fa8ff"))
    p.setColor(QPalette.HighlightedText, c("#ffffff"))
    p.setColor(QPalette.Link, c("#5fa8ff"))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        p.setColor(QPalette.Disabled, role, c("#666666"))
    app.setPalette(p)