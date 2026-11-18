"""Session log of recognized Japanese and its English, one tab per region."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from lisktranslate.furigana import Token
from lisktranslate.panel import _Flow


class _Row:
    def __init__(self, japanese: str, english: str, tokens: list[Token] | None, width: int) -> None:
        self.japanese = japanese
        self.english = english.strip()
        self.block = QWidget()
        layout = QVBoxLayout(self.block)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)
        self.flow: _Flow | None = None
        self.source: QLabel | None = None
        if tokens:
            self.flow = _Flow(tail=2)
            self.flow.setFixedWidth(width)
            self.flow.set_tokens(tokens, show_readings=True, reading_size=7, surface_size=13, pad_right=1)
            layout.addWidget(self.flow)
        else:
            self.source = QLabel(japanese)
            self.source.setWordWrap(True)
            self.source.setFont(QFont("Yu Gothic UI", 13))
            self.source.setStyleSheet("color: #ececec;")
            self.source.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.source.setFixedWidth(width)
            layout.addWidget(self.source)
        self.english_label = QLabel(self.english)
        self.english_label.setWordWrap(True)
        self.english_label.setFont(QFont("Segoe UI", 11))
        self.english_label.setStyleSheet("color: #d6e4dc;")
        self.english_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.english_label.setFixedWidth(width)
        self.english_label.setVisible(bool(self.english))
        layout.addWidget(self.english_label)

    def set_width(self, width: int) -> None:
        if self.flow is not None:
            self.flow.setFixedWidth(width)
        if self.source is not None:
            self.source.setFixedWidth(width)
        self.english_label.setFixedWidth(width)

    def set_english(self, english: str) -> None:
        english = english.strip()
        if not english or english == self.english:
            return
        self.english = english
        self.english_label.setText(english)
        self.english_label.show()


class _Page(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._stick = True
        self.entries: list[_Row] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.holder = QWidget()
        self.sections = QVBoxLayout(self.holder)
        self.sections.setContentsMargins(0, 0, 0, 0)
        self.sections.setSpacing(8)
        self.placeholder = QLabel("Lines from this region show up here.")
        self.placeholder.setWordWrap(True)
        self.placeholder.setStyleSheet("color: #8b8d93;")
        self.sections.addWidget(self.placeholder)
        self.sections.addStretch(1)
        self.scroll.setWidget(self.holder)
        layout.addWidget(self.scroll)
        bar = self.scroll.verticalScrollBar()
        bar.valueChanged.connect(self._on_scrolled)
        bar.rangeChanged.connect(self._on_range)

    def add_line(self, japanese: str, english: str, tokens: list[Token] | None) -> None:
        japanese = japanese.strip()
        if not japanese:
            return
        if self.entries and self.entries[-1].japanese == japanese:
            self.entries[-1].set_english(english)
            return
        self.placeholder.hide()
        row = _Row(japanese, english, tokens, self._content_width())
        self.entries.append(row)
        self.sections.insertWidget(self.sections.count() - 1, row.block)

    def set_english(self, japanese: str, english: str) -> None:
        japanese = japanese.strip()
        english = english.strip()
        if not japanese or not english:
            return
        for row in reversed(self.entries):
            if row.japanese == japanese:
                row.set_english(english)
                return

    def apply_width(self) -> None:
        width = self._content_width()
        for row in self.entries:
            row.set_width(width)

    def scroll_to_end(self) -> None:
        if not self._stick:
            return
        bar = self.scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _content_width(self) -> int:
        return max(40, self.scroll.viewport().width() - 8)

    def _on_scrolled(self, value: int) -> None:
        bar = self.scroll.verticalScrollBar()
        self._stick = value >= bar.maximum() - 8

    def _on_range(self, _minimum: int, maximum: int) -> None:
        if self._stick:
            self.scroll.verticalScrollBar().setValue(maximum)


class HistoryWindow(QWidget):
    closed = Signal()
    folder_picked = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("History")
        self.setWindowFlag(Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)
        self.resize(380, 580)
        self._force_close = False
        self._folder = ""
        self._pages: dict[str, _Page] = {}
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(6)
        folder_row = QHBoxLayout()
        self.folder_button = QPushButton("Choose folder")
        self.folder_button.setToolTip("Save history here, one file per region")
        self.folder_button.clicked.connect(self._pick_folder)
        self.folder_label = QLabel("History is not saved yet")
        self.folder_label.setStyleSheet("color: #8b8d93;")
        self.folder_label.setWordWrap(False)
        folder_row.addWidget(self.folder_button)
        folder_row.addWidget(self.folder_label, 1)
        root.addLayout(folder_row)
        self.placeholder = QLabel("Lines from this session show up here.")
        self.placeholder.setWordWrap(True)
        self.placeholder.setStyleSheet("color: #8b8d93;")
        self.tabs = QTabWidget()
        self.tabs.hide()
        root.addWidget(self.placeholder)
        root.addWidget(self.tabs, 1)

    def set_folder(self, path: str) -> None:
        self._folder = path or ""
        if not self._folder:
            self.folder_label.setText("History is not saved yet")
            self.folder_label.setToolTip("")
            return
        parts = [part for part in self._folder.replace("\\", "/").split("/") if part]
        shown = "/".join(parts[-2:]) if len(parts) > 2 else self._folder
        self.folder_label.setText(shown)
        self.folder_label.setToolTip(self._folder)

    def page(self, region: str) -> _Page:
        return self._pages[region]

    def add_line(self, region: str, japanese: str, english: str, tokens: list[Token] | None) -> None:
        region = region.strip() or "Region"
        japanese = japanese.strip()
        if not japanese:
            return
        page = self._ensure_page(region)
        page.add_line(japanese, english, tokens)

    def set_english(self, region: str, japanese: str, english: str) -> None:
        page = self._pages.get(region.strip() or "Region")
        if page is not None:
            page.set_english(japanese, english)

    def force_close(self) -> None:
        self._force_close = True
        self.close()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        for page in self._pages.values():
            page.apply_width()
            if page._stick:
                QTimer.singleShot(0, page.scroll_to_end)

    def closeEvent(self, event) -> None:
        if self._force_close:
            event.accept()
            return
        event.ignore()
        self.hide()
        self.closed.emit()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        for page in self._pages.values():
            page.apply_width()

    def _ensure_page(self, region: str) -> _Page:
        page = self._pages.get(region)
        if page is not None:
            return page
        page = _Page()
        self._pages[region] = page
        self.tabs.addTab(page, region)
        self.placeholder.hide()
        self.tabs.show()
        return page

    def _pick_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Choose a history folder", self._folder)
        if not path:
            return
        self.set_folder(path)
        self.folder_picked.emit(path)
