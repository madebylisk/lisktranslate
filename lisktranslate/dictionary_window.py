"""Separate window for kanji, readings, and meanings."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from lisktranslate.dictionary import DictionaryPage


class DictionaryWindow(QWidget):
    closed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Dictionary")
        self.setWindowFlag(Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)
        self.resize(400, 580)
        self._force_close = False
        self.has_page = False
        self._wrap_labels: list[QLabel] = []
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 10)
        root.setSpacing(8)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.holder = QWidget()
        self.sections = QVBoxLayout(self.holder)
        self.sections.setContentsMargins(0, 0, 0, 0)
        self.sections.setSpacing(14)
        self.sections.addStretch(1)
        self.scroll.setWidget(self.holder)
        root.addWidget(self.scroll, 1)
        footer = QLabel("JMdict and KANJIDIC2 by the EDRDG, CC BY-SA")
        footer.setWordWrap(True)
        footer.setStyleSheet("color: #8b8d93;")
        footer.setFont(QFont("Segoe UI", 8))
        root.addWidget(footer)
        self.show_message("Kanji from the recognized text show up here.")

    def show_message(self, text: str) -> None:
        self.has_page = False
        self._fill([(text, True)])

    def show_page(self, page: DictionaryPage) -> None:
        if not page.words and not page.kanji:
            self._fill([("No kanji in this text.", True)])
            self.has_page = True
            return
        self.has_page = True
        self._render(page)

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
        width = max(40, self.scroll.viewport().width() - 8)
        for label in self._wrap_labels:
            label.setFixedWidth(width)

    def _render(self, page: DictionaryPage) -> None:
        self._clear()
        width = max(40, self.scroll.viewport().width() - 8)
        if page.words:
            self.sections.addWidget(self._heading("Words"))
            for word in page.words:
                self.sections.addWidget(self._word_block(word.written, word.reading, word.meanings, width))
        if page.kanji:
            self.sections.addWidget(self._heading("Kanji"))
            for kanji in page.kanji:
                self.sections.addWidget(self._word_block(kanji.character, kanji.readings, kanji.meanings, width, large=True))
        self.sections.addStretch(1)

    def _fill(self, rows: list[tuple[str, bool]]) -> None:
        self._clear()
        for text, muted in rows:
            label = QLabel(text)
            label.setWordWrap(True)
            label.setStyleSheet("color: #8b8d93;" if muted else "color: #ececec;")
            self.sections.addWidget(label)
        self.sections.addStretch(1)

    def _heading(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setFont(QFont("Segoe UI", 9))
        label.setStyleSheet("color: #a1a1aa;")
        return label

    def _word_block(self, written: str, reading: str, meanings: str, width: int, large: bool = False) -> QWidget:
        block = QWidget()
        layout = QVBoxLayout(block)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        line = QHBoxLayout()
        line.setSpacing(10)
        head = QLabel(written)
        head.setFont(QFont("Yu Gothic UI", 16 if large else 15))
        head.setStyleSheet("color: #ececec;")
        head.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        reading_label = QLabel(reading)
        reading_label.setFont(QFont("Yu Gothic UI", 11))
        reading_label.setStyleSheet("color: #a7f3d0;")
        reading_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        reading_label.setWordWrap(True)
        line.addWidget(head, 0, Qt.AlignmentFlag.AlignTop)
        line.addWidget(reading_label, 1, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(line)
        meaning = QLabel(meanings)
        meaning.setWordWrap(True)
        meaning.setFont(QFont("Segoe UI", 11))
        meaning.setStyleSheet("color: #d6d6da;")
        meaning.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        meaning.setFixedWidth(width)
        self._wrap_labels.append(meaning)
        self._wrap_labels.append(reading_label)
        layout.addWidget(meaning)
        return block

    def _clear(self) -> None:
        self._wrap_labels.clear()
        while self.sections.count():
            item = self.sections.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
            nested = item.layout()
            if nested is not None:
                self._clear_layout(nested)

    def _clear_layout(self, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
