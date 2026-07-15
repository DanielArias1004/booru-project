# ui/settings_widget.py
import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFileDialog
)
from PySide6.QtCore import Qt, Signal
from services.config_handler import get_base_folders, add_base_folder, remove_base_folder


class SettingsWidget(QWidget):
    """Settings as an embedded page widget, not a dialog."""
    folders_changed = Signal()  # emitted when base folders are added/removed

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 32, 40, 32)
        layout.setAlignment(Qt.AlignTop)
        layout.setSpacing(8)

        title = QLabel("Settings")
        title.setStyleSheet(
            "font-size: 22px; font-weight: bold; margin-bottom: 20px;"
        )
        layout.addWidget(title)

        section = QLabel("Base Folders")
        section.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #ccc;"
        )
        layout.addWidget(section)

        hint = QLabel(
            "All images inside these folders appear in the browse grid."
        )
        hint.setStyleSheet("color: #777; margin-bottom: 8px; font-size: 12px;")
        layout.addWidget(hint)

        self._folder_container = QWidget()
        self._folder_layout = QVBoxLayout(self._folder_container)
        self._folder_layout.setContentsMargins(0, 0, 0, 0)
        self._folder_layout.setSpacing(4)
        layout.addWidget(self._folder_container)

        add_btn = QPushButton("+ Add Base Folder")
        add_btn.setFixedWidth(180)
        add_btn.clicked.connect(self._add_folder)
        layout.addSpacing(8)
        layout.addWidget(add_btn)
        layout.addStretch()

        self._refresh()

    def _refresh(self) -> None:
        for i in reversed(range(self._folder_layout.count())):
            w = self._folder_layout.itemAt(i).widget()
            if w:
                w.setParent(None)

        folders = get_base_folders()
        if not folders:
            empty = QLabel("No base folders added yet.")
            empty.setStyleSheet("color: #555; padding: 4px;")
            self._folder_layout.addWidget(empty)
            return

        for folder in folders:
            row = QWidget()
            row.setStyleSheet(
                "background: #1e1e1e; border-radius: 4px;"
            )
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(8, 4, 4, 4)

            label = QLabel(folder)
            label.setStyleSheet("color: #ccc; font-size: 12px;")
            row_layout.addWidget(label, stretch=1)

            rem = QPushButton("✕")
            rem.setFixedSize(26, 26)
            rem.setToolTip("Remove this base folder")
            rem.setStyleSheet(
                "QPushButton { background: transparent; color: #777; border: none; }"
                "QPushButton:hover { color: #ff6b6b; }"
            )
            rem.clicked.connect(lambda _, f=folder: self._remove_folder(f))
            row_layout.addWidget(rem)

            self._folder_layout.addWidget(row)

    def _add_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Add Base Folder")
        if folder:
            add_base_folder(folder)
            self._refresh()
            self.folders_changed.emit()

    def _remove_folder(self, folder: str) -> None:
        remove_base_folder(folder)
        self._refresh()
        self.folders_changed.emit()

    def showEvent(self, event) -> None:
        """Refresh folder list every time this page becomes visible."""
        super().showEvent(event)
        self._refresh()