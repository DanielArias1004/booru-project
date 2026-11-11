# ui/canvas/sidebar.py
import os
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QScrollArea, QMenu,
    QInputDialog, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

from services.db_handler import (
    set_favorite, get_favorite, get_image_id_by_path,
    get_latest_note, add_note,
    get_pools, create_pool, add_image_to_pool,
    remove_image_from_pool, get_pool_ids_for_image
)

_BTN_STYLE = """
    QPushButton { background: #2a2a2a; color: #ddd; border: 1px solid #444;
                  border-radius: 6px; padding: 7px; font-size: 13px; }
    QPushButton:hover { background: #333; }
"""
_FAV_ON_STYLE = """
    QPushButton { background: #3a1a1a; color: #ff6b6b; border: 1px solid #ff6b6b55;
                  border-radius: 6px; padding: 7px; font-size: 13px; }
    QPushButton:hover { background: #4a2020; }
"""

class CollapsibleSection(QWidget):
    """
    A section with a clickable header that shows/hides its content.
    Used to build the collapsible sidebar panels.
    """

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self._expanded = True

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 4)
        layout.setSpacing(0)

        # Header row
        self._header = QPushButton(f"▾  {title}")
        self._header.setCheckable(True)
        self._header.setChecked(True)
        self._header.setStyleSheet("""
            QPushButton {
                background: #252525;
                color: #cccccc;
                border: none;
                border-top: 1px solid #333;
                padding: 6px 10px;
                text-align: left;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover { background: #2e2e2e; }
        """)
        self._header.clicked.connect(self._toggle)
        layout.addWidget(self._header)

        # Content widget
        self._content = QWidget()
        self._content.setStyleSheet("background: #1e1e1e;")
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(8, 6, 8, 8)
        self._content_layout.setSpacing(4)
        layout.addWidget(self._content)

    def add_widget(self, widget: QWidget) -> None:
        self._content_layout.addWidget(widget)

    def content_layout(self) -> QVBoxLayout:
        return self._content_layout

    def _toggle(self, checked: bool) -> None:
        self._expanded = checked
        self._content.setVisible(checked)
        title = self._header.text()[3:]  # strip old arrow
        self._header.setText(f"{'▾' if checked else '▸'}  {title}")


class FlowLayout(QVBoxLayout):
    """
    Simple tag chip container. Chips wrap into a QVBoxLayout of
    QHBoxLayout rows — proper flow layout is complex in Qt, this
    approximation works fine for a sidebar width.
    """
    pass


class CanvasSidebar(QWidget):
    """
    Right sidebar for the canvas. Contains collapsible sections:
    - Favorites (heart button)
    - File Info (name, type, size, dates)
    - Notes (markdown edit + preview toggle)
    """
    note_saved = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._image_id: int | None = None
        self._image_path: str = ""
        self._is_favorite: bool = False
        self._preview_mode: bool = False

        self.setMinimumWidth(220)
        self.setMaximumWidth(500)
        self.resize(280, self.height())

        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Header with hide button
        header = QWidget()
        header.setFixedHeight(36)
        header.setStyleSheet("background: #1a1a1a; border-bottom: 1px solid #333;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 0, 6, 0)
        title_lbl = QLabel("Info")
        title_lbl.setStyleSheet("color: #aaa; font-weight: bold; font-size: 12px;")
        header_layout.addWidget(title_lbl)
        header_layout.addStretch()
        outer.addWidget(header)

        # Scrollable content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: #1a1a1a; }")

        content = QWidget()
        content.setStyleSheet("background: #1a1a1a;")
        self._main_layout = QVBoxLayout(content)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(0)

        self._build_action_buttons()
        self._build_file_info_section()
        self._build_notes_section()

        self._main_layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll, stretch=1)

    # — Section builders —

    def _build_action_buttons(self) -> None:
        holder = QWidget()
        row = QHBoxLayout(holder)
        row.setContentsMargins(8, 8, 8, 8)
        row.setSpacing(6)

        self._fav_btn = QPushButton()
        self._fav_btn.clicked.connect(self._toggle_favorite)
        self._pool_btn = QPushButton("＋  Pool")
        self._pool_btn.setStyleSheet(_BTN_STYLE)
        self._pool_btn.clicked.connect(self._show_pool_menu)

        row.addWidget(self._fav_btn, stretch=1)
        row.addWidget(self._pool_btn, stretch=1)
        self._main_layout.addWidget(holder)
        self._update_fav_button()

    def _build_file_info_section(self) -> None:
        section = CollapsibleSection("File Info")
        self._info_labels: dict[str, QLabel] = {}
        for key in ("Name", "Type", "Size", "Modified", "Created"):
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(4)
            key_lbl = QLabel(f"{key}:")
            key_lbl.setFixedWidth(64)
            key_lbl.setStyleSheet("color: #999; font-size: 11px;")
            val_lbl = QLabel("—")
            val_lbl.setWordWrap(True)
            val_lbl.setStyleSheet("color: #ccc; font-size: 11px;")
            val_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
            row_layout.addWidget(key_lbl)
            row_layout.addWidget(val_lbl, stretch=1)
            section.add_widget(row)
            self._info_labels[key] = val_lbl
        self._main_layout.addWidget(section)

    def _build_notes_section(self) -> None:
        section = CollapsibleSection("Notes")

        # Edit / Preview toggle
        toggle_row = QWidget()
        toggle_layout = QHBoxLayout(toggle_row)
        toggle_layout.setContentsMargins(0, 0, 0, 0)
        toggle_layout.setSpacing(4)

        self._edit_btn = QPushButton("Edit")
        self._preview_btn = QPushButton("Preview")
        for btn in (self._edit_btn, self._preview_btn):
            btn.setCheckable(True)
            btn.setFixedHeight(24)
            btn.setStyleSheet("""
                QPushButton {
                    background: #2a2a2a;
                    color: #888;
                    border: 1px solid #444;
                    border-radius: 4px;
                    padding: 0 10px;
                    font-size: 11px;
                }
                QPushButton:checked {
                    background: #5fa8ff;
                    color: white;
                    border-color: #5fa8ff;
                }
            """)
        self._edit_btn.setChecked(True)
        self._edit_btn.clicked.connect(lambda: self._set_preview(False))
        self._preview_btn.clicked.connect(lambda: self._set_preview(True))
        toggle_layout.addWidget(self._edit_btn)
        toggle_layout.addWidget(self._preview_btn)
        toggle_layout.addStretch()
        section.add_widget(toggle_row)

        # Edit area
        self._notes_edit = QTextEdit()
        self._notes_edit.setPlaceholderText(
            "Write notes in Markdown…\n\n"
            "**bold**, *italic*, # Header, - list item"
        )
        self._notes_edit.setMinimumHeight(160)
        self._notes_edit.setStyleSheet("""
            QTextEdit {
                background: #222;
                color: #ddd;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 6px;
                font-family: monospace;
                font-size: 12px;
            }
        """)
        self._notes_edit.textChanged.connect(self._on_note_changed)
        section.add_widget(self._notes_edit)

        # Preview area
        from PySide6.QtWidgets import QTextBrowser
        self._notes_preview = QTextBrowser()
        self._notes_preview.setMinimumHeight(160)
        self._notes_preview.setOpenExternalLinks(True)
        self._notes_preview.setStyleSheet("""
            QTextBrowser {
                background: #222;
                color: #ddd;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 6px;
                font-size: 12px;
            }
        """)
        self._notes_preview.setVisible(False)
        section.add_widget(self._notes_preview)

        # Save button
        save_btn = QPushButton("Save Notes")
        save_btn.setStyleSheet("""
            QPushButton {
                background: #2a5a2a;
                color: #aaffaa;
                border: 1px solid #3a7a3a;
                border-radius: 4px;
                padding: 5px;
                font-size: 12px;
            }
            QPushButton:hover { background: #336633; }
        """)
        save_btn.clicked.connect(self._save_note)
        section.add_widget(save_btn)

        self._main_layout.addWidget(section)

    # — Public API —

    def load_image(self, image_path: str) -> None:
        """Call this every time the canvas switches to a new image."""
        self._save_note()  # save previous image's note before switching
        self._image_path = image_path
        self._image_id = get_image_id_by_path(image_path)
        self._refresh_all()

    def save(self) -> None:
        """Call when navigating away from canvas."""
        self._save_note()

    # — Internal refresh —

    def _refresh_all(self) -> None:
        self._refresh_file_info()
        self._refresh_notes()
        self._refresh_favorite()

    def _refresh_file_info(self) -> None:
        path = self._image_path
        if not path or not os.path.exists(path):
            for lbl in self._info_labels.values():
                lbl.setText("—")
            return

        stat = os.stat(path)
        size_bytes = stat.st_size
        if size_bytes < 1024:
            size_str = f"{size_bytes} B"
        elif size_bytes < 1024 ** 2:
            size_str = f"{size_bytes / 1024:.1f} KB"
        else:
            size_str = f"{size_bytes / 1024**2:.1f} MB"

        self._info_labels["Name"].setText(os.path.basename(path))
        self._info_labels["Type"].setText(os.path.splitext(path)[1].upper().lstrip("."))
        self._info_labels["Size"].setText(size_str)
        self._info_labels["Modified"].setText(
            datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
        )
        # st_birthtime on macOS, st_ctime on Windows (close enough)
        created_ts = getattr(stat, "st_birthtime", stat.st_ctime)
        self._info_labels["Created"].setText(
            datetime.fromtimestamp(created_ts).strftime("%Y-%m-%d %H:%M")
        )

    def _refresh_notes(self) -> None:
        if self._image_id:
            note = get_latest_note(self._image_id) or ""
        else:
            note = ""
        self._notes_edit.blockSignals(True)
        self._notes_edit.setPlainText(note)
        self._notes_edit.blockSignals(False)
        if self._preview_mode:
            self._render_preview()

    def _refresh_favorite(self) -> None:
        if self._image_id:
            self._is_favorite = get_favorite(self._image_id)
        else:
            self._is_favorite = False
        self._update_fav_button()

    # — Notes actions —

    def _on_note_changed(self) -> None:
        if self._preview_mode:
            self._render_preview()

    def _set_preview(self, preview: bool) -> None:
        self._preview_mode = preview
        self._edit_btn.setChecked(not preview)
        self._preview_btn.setChecked(preview)
        self._notes_edit.setVisible(not preview)
        self._notes_preview.setVisible(preview)
        if preview:
            self._render_preview()

    def _render_preview(self) -> None:
        try:
            import markdown
            html = markdown.markdown(
                self._notes_edit.toPlainText(),
                extensions=["nl2br", "fenced_code"]
            )
        except ImportError:
            # markdown package not installed — show plain text
            html = f"<pre>{self._notes_edit.toPlainText()}</pre>"
        self._notes_preview.setHtml(f"""
            <style>
                body {{ color: #ddd; font-family: sans-serif;
                       font-size: 12px; line-height: 1.6; }}
                code {{ background: #333; padding: 2px 4px;
                        border-radius: 3px; }}
                pre  {{ background: #333; padding: 8px;
                        border-radius: 4px; overflow-x: auto; }}
                h1, h2, h3 {{ color: #5fa8ff; }}
            </style>
            {html}
        """)

    def _save_note(self) -> None:
        if not self._image_id:
            return
        add_note(
            self._image_id,
            self._notes_edit.toPlainText(),
            datetime.now().isoformat()
        )
        self.note_saved.emit()

    # — Favorites —

    def _toggle_favorite(self) -> None:
        if not self._image_id:
            return
        self._is_favorite = not self._is_favorite
        set_favorite(self._image_id, self._is_favorite)
        self._update_fav_button()

    def _update_fav_button(self) -> None:
        if self._is_favorite:
            self._fav_btn.setText("♥  Favorited")
            self._fav_btn.setStyleSheet(_FAV_ON_STYLE)
        else:
            self._fav_btn.setText("♡  Favorite")
            self._fav_btn.setStyleSheet(_BTN_STYLE)

    def _show_pool_menu(self) -> None:
        if not self._image_id:
            return
        member_of = get_pool_ids_for_image(self._image_id)
        menu = QMenu(self)
        for pool in get_pools():
            action = menu.addAction(pool["name"])
            action.setCheckable(True)
            action.setChecked(pool["id"] in member_of)
            action.setData(pool["id"])
        menu.addSeparator()
        new_action = menu.addAction("＋  New pool…")

        chosen = menu.exec(self._pool_btn.mapToGlobal(self._pool_btn.rect().bottomLeft()))
        if chosen is None:
            return
        if chosen == new_action:
            name, ok = QInputDialog.getText(self, "New Pool", "Pool name:")
            if ok and name.strip():
                pool_id = create_pool(name)
                if pool_id is None:
                    QMessageBox.warning(self, "New Pool", "That name is empty or already taken.")
                else:
                    add_image_to_pool(pool_id, self._image_id)
            return
        pool_id = chosen.data()
        if pool_id in member_of:
            remove_image_from_pool(pool_id, self._image_id)
        else:
            add_image_to_pool(pool_id, self._image_id)