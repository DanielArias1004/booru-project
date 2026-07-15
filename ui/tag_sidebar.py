# ui/tag_sidebar.py
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QScrollArea, QComboBox
)
from PySide6.QtCore import Qt, Signal

from services.db_handler import get_all_tags_with_counts

TAG_TYPE_COLORS = {
    "copyright": "#c060c0",
    "character":  "#00aa00",
    "artist":     "#cc6633",
    "general":    "#5588bb",
    "meta":       "#ffaa00",
    "other":      "#888888",
}


class TagSidebar(QWidget):
    """
    Left sidebar on the browse page.
    Shows all tags with counts, search, sort controls.
    Emitting tag_clicked lets browse_widget filter the grid.
    Emitting search_submitted lets browse_widget do a tag search.
    """
    tag_clicked = Signal(str)       # tag name clicked
    search_submitted = Signal(str)  # search bar submitted

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(220)
        self._all_tags: list[dict] = []
        self._sort_by: str = "count"  # "count", "name", "type"
        self._ascending: bool = False
        self._active_tags: set[str] = set()  # currently selected filter tags
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QWidget()
        header.setStyleSheet("background: #141414; border-bottom: 1px solid #2a2a2a;")
        header.setFixedHeight(36)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 0, 10, 0)
        lbl = QLabel("Tags")
        lbl.setStyleSheet("color: #aaa; font-weight: bold; font-size: 12px;")
        header_layout.addWidget(lbl)
        header_layout.addStretch()

        self._count_lbl = QLabel("0")
        self._count_lbl.setStyleSheet("color: #555; font-size: 11px;")
        header_layout.addWidget(self._count_lbl)
        layout.addWidget(header)

        # Search bar
        search_widget = QWidget()
        search_widget.setStyleSheet("background: #1a1a1a; padding: 6px;")
        search_layout = QVBoxLayout(search_widget)
        search_layout.setContentsMargins(8, 6, 8, 6)
        search_layout.setSpacing(6)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search tags…")
        self._search.setStyleSheet("""
            QLineEdit {
                background: #2a2a2a;
                color: #ddd;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 5px 8px;
                font-size: 12px;
            }
            QLineEdit:focus { border-color: #5fa8ff; }
        """)
        self._search.textChanged.connect(self._filter_display)
        self._search.returnPressed.connect(
            lambda: self.search_submitted.emit(self._search.text().strip())
        )
        search_layout.addWidget(self._search)

        # Sort controls
        sort_row = QHBoxLayout()
        sort_row.setSpacing(4)

        self._sort_combo = QComboBox()
        self._sort_combo.addItems(["Count", "Name", "Type"])
        self._sort_combo.setStyleSheet("""
            QComboBox {
                background: #2a2a2a;
                color: #ccc;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 11px;
            }
        """)
        self._sort_combo.currentTextChanged.connect(self._on_sort_changed)

        self._asc_btn = QPushButton("↑")
        self._asc_btn.setCheckable(True)
        self._asc_btn.setFixedSize(28, 24)
        self._asc_btn.setToolTip("Ascending / Descending")
        self._asc_btn.setStyleSheet("""
            QPushButton {
                background: #2a2a2a;
                color: #888;
                border: 1px solid #444;
                border-radius: 4px;
                font-size: 13px;
            }
            QPushButton:checked { color: #5fa8ff; border-color: #5fa8ff; }
        """)
        self._asc_btn.clicked.connect(self._on_sort_changed)

        clear_btn = QPushButton("Clear")
        clear_btn.setFixedHeight(24)
        clear_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #666;
                border: none;
                font-size: 11px;
            }
            QPushButton:hover { color: #aaa; }
        """)
        clear_btn.clicked.connect(self._clear_filters)

        sort_row.addWidget(self._sort_combo, stretch=1)
        sort_row.addWidget(self._asc_btn)
        sort_row.addWidget(clear_btn)
        search_layout.addLayout(sort_row)
        layout.addWidget(search_widget)

        # Tag list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: #1a1a1a; }")

        self._list_widget = QWidget()
        self._list_widget.setStyleSheet("background: #1a1a1a;")
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(0, 4, 0, 4)
        self._list_layout.setSpacing(1)
        self._list_layout.setAlignment(Qt.AlignTop)

        scroll.setWidget(self._list_widget)
        layout.addWidget(scroll, stretch=1)

    # — Public API —

    def refresh(self) -> None:
        """Reload tags from DB and redisplay."""
        self._all_tags = get_all_tags_with_counts()
        self._count_lbl.setText(f"{len(self._all_tags)} tags")
        self._filter_display()

    def get_active_tags(self) -> list[str]:
        return list(self._active_tags)

    # — Internal —

    def _filter_display(self) -> None:
        query = self._search.text().strip().lower()
        tags = self._all_tags

        if query:
            tags = [t for t in tags if query in t["name"]]

        sort_key = self._sort_combo.currentText().lower()
        reverse = not self._asc_btn.isChecked()

        if sort_key == "count":
            tags = sorted(tags, key=lambda t: t["count"], reverse=reverse)
        elif sort_key == "name":
            tags = sorted(tags, key=lambda t: t["name"], reverse=reverse)
        elif sort_key == "type":
            tags = sorted(tags, key=lambda t: (t["type"], t["name"]), reverse=reverse)

        self._rebuild_list(tags)

    def _rebuild_list(self, tags: list[dict]) -> None:
        for i in reversed(range(self._list_layout.count())):
            w = self._list_layout.itemAt(i).widget()
            if w:
                w.setParent(None)

        for tag in tags:
            row = self._make_tag_row(tag)
            self._list_layout.addWidget(row)

    def _make_tag_row(self, tag: dict) -> QWidget:
        row = QWidget()
        is_active = tag["name"] in self._active_tags
        color = TAG_TYPE_COLORS.get(tag["type"], "#888")

        row.setStyleSheet(f"""
            QWidget {{
                background: {"#1e2a1e" if is_active else "transparent"};
                border-left: 3px solid {color if is_active else "transparent"};
            }}
            QWidget:hover {{ background: #252525; }}
        """)

        layout = QHBoxLayout(row)
        layout.setContentsMargins(12, 3, 8, 3)
        layout.setSpacing(6)

        name_lbl = QLabel(tag["name"])
        name_lbl.setStyleSheet(f"color: {color}; font-size: 12px; border: none;")
        layout.addWidget(name_lbl, stretch=1)

        count_lbl = QLabel(str(tag["count"]))
        count_lbl.setStyleSheet("color: #555; font-size: 11px; border: none;")
        layout.addWidget(count_lbl)

        row.mousePressEvent = lambda _e, t=tag["name"]: self._on_tag_clicked(t)
        return row

    def _on_tag_clicked(self, name: str) -> None:
        if name in self._active_tags:
            self._active_tags.discard(name)
        else:
            self._active_tags.add(name)
        self.tag_clicked.emit(name)
        self._filter_display()

    def _on_sort_changed(self) -> None:
        self._filter_display()

    def _clear_filters(self) -> None:
        self._active_tags.clear()
        self._search.clear()
        self._filter_display()
        self.tag_clicked.emit("")  # signal browse to show all