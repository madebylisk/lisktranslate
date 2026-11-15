"""Session log of recognized Japanese and its English."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QLabel, QScrollArea, QVBoxLayout, QWidget

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


class HistoryWindow(QWidget):
    closed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("History")
        self.setWindowFlag(Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)
        self.resize(380, 580)
        self._force_close = False
        self._stick = True
        self.entries: list[_Row] = []
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(6)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.holder = QWidget()
        self.sections = QVBoxLayout(self.holder)
        self.sections.setContentsMargins(0, 0, 0, 0)
        self.sections.setSpacing(8)
        self.placeholder = QLabel("Lines from this session show up here.")
        self.placeholder.setWordWrap(True)
        self.placeholder.setStyleSheet("color: #8b8d93;")
        self.sections.addWidget(self.placeholder)
        self.sections.addStretch(1)
        self.scroll.setWidget(self.holder)
        root.addWidget(self.scroll, 1)
        bar = self.scroll.verticalScrollBar()
        bar.valueChanged.connect(self._on_scrolled)
        bar.rangeChanged.connect(self._on_range)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        width = self._content_width()
        for row in self.entries:
            row.set_width(width)
        if self._stick:
            QTimer.singleShot(0, self._scroll_to_end)

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

    def force_close(self) -> None:
        self._force_close = True
        self.close()

    def closeEvent(self, event) -> None:
        if self._force_close:
            event.accept()
            return
        event.ignore()
        self.hide()
        self.closed.emit()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        width = self._content_width()
        for row in self.entries:
            row.set_width(width)

    def _content_width(self) -> int:
        return max(40, self.scroll.viewport().width() - 8)

    def _on_scrolled(self, value: int) -> None:
        bar = self.scroll.verticalScrollBar()
        self._stick = value >= bar.maximum() - 8

    def _on_range(self, _minimum: int, maximum: int) -> None:
        if self._stick:
            self.scroll.verticalScrollBar().setValue(maximum)

    def _scroll_to_end(self) -> None:
        bar = self.scroll.verticalScrollBar()
        bar.setValue(bar.maximum())
