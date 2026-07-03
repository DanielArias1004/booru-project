# ui/browse/settings_dialog.py
import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFileDialog, QWidget
)
from PySide6.QtCore import Qt
from services.config_handler import get_base_folders, add_base_folder, remove_base_folder


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(500)
        self.setModal(True)  # blocks interaction with parent window while open

        layout = QVBoxLayout(self)

        # Section header
        header = QLabel("Base Folders")
        header.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 4px;")
        layout.addWidget(header)

        hint = QLabel("Images from these folders will appear in the browse grid.")
        hint.setStyleSheet("color: gray; margin-bottom: 8px;")
        layout.addWidget(hint)

        # This widget holds the dynamic list of base folders
        self._folder_list_widget = QWidget()
        self._folder_list_layout = QVBoxLayout(self._folder_list_widget)
        self._folder_list_layout.setContentsMargins(0, 0, 0, 0)
        self._folder_list_layout.setSpacing(4)
        layout.addWidget(self._folder_list_widget)

        # Add folder button
        add_btn = QPushButton("+ Add Base Folder")
        add_btn.clicked.connect(self._add_folder)
        layout.addWidget(add_btn)

        layout.addStretch()

        # Close button
        close_btn = QPushButton("Done")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

        self._refresh_list()

    def _refresh_list(self) -> None:
        """Rebuild the folder list with remove buttons."""
        for i in reversed(range(self._folder_list_layout.count())):
            w = self._folder_list_layout.itemAt(i).widget()
            if w:
                w.setParent(None)

        folders = get_base_folders()
        if not folders:
            empty = QLabel("No base folders added yet.")
            empty.setStyleSheet("color: gray;")
            self._folder_list_layout.addWidget(empty)
            return

        for folder in folders:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)

            label = QLabel(folder)
            label.setStyleSheet("padding: 4px;")
            # make label truncate gracefully if path is long
            label.setWordWrap(False)
            label.setSizePolicy(
                label.sizePolicy().horizontalPolicy(),
                label.sizePolicy().verticalPolicy()
            )
            row_layout.addWidget(label, stretch=1)

            rem_btn = QPushButton("✕")
            rem_btn.setFixedSize(28, 28)
            rem_btn.setToolTip(f"Remove {folder}")
            rem_btn.clicked.connect(lambda _checked, f=folder: self._remove_folder(f))
            row_layout.addWidget(rem_btn)

            self._folder_list_layout.addWidget(row)

    def _add_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose Base Folder")
        if folder:
            add_base_folder(folder)
            self._refresh_list()

    def _remove_folder(self, folder: str) -> None:
        remove_base_folder(folder)
        self._refresh_list()