"""Text panel. Furigana is drawn above kanji; Qt's text widget has no ruby tags."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import QFrame, QLabel, QScrollArea, QSizePolicy, QVBoxLayout, QWidget

from lisktranslate.furigana import Token


class RubyWord(QWidget):
    def __init__(self, surface: str, reading: str | None) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 0, 3, 0)
        layout.setSpacing(0)
        self.reading = QLabel(reading or " ")
        self.reading.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom)
        self.reading.setFont(QFont("Yu Gothic UI", 8))
        self.surface = QLabel(surface)
        self.surface.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.surface.setFont(QFont("Yu Gothic UI", 15))
        self.surface.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.reading.setStyleSheet("color: #a7f3d0;" if reading else "color: transparent;")
        self.reading.setFixedHeight(QFontMetrics(self.reading.font()).height())
        layout.addWidget(self.reading)
        layout.addWidget(self.surface)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def sizeHint(self):
        hint = super().sizeHint()
        return hint


class _Flow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._items: list[QWidget | None] = []

    def set_tokens(self, tokens: list[Token]) -> None:
        for item in self._items:
            if item is not None:
                item.setParent(None)
                item.deleteLater()
        self._items = []
        for token in tokens:
            if token.break_line:
                self._items.append(None)
                continue
            if token.header:
                label = QLabel(token.surface)
                label.setFont(QFont("Yu Gothic UI", 9))
                label.setStyleSheet("color: #a1a1aa;")
                label.setParent(self)
                self._items.append(label)
                self._items.append(None)
                continue
            word = RubyWord(token.surface, token.reading)
            word.setParent(self)
            self._items.append(word)
        self._layout_rows()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._layout_rows()

    def _layout_rows(self) -> None:
        width = max(self.width(), 1)
        x = 0
        y = 0
        line_height = 0
        for item in self._items:
            if item is None:
                x = 0
                y += line_height
                line_height = 0
                continue
            hint = item.sizeHint()
            item.resize(hint)
            if x > 0 and x + hint.width() > width:
                x = 0
                y += line_height
                line_height = 0
            item.move(x, y)
            item.show()
            x += hint.width()
            line_height = max(line_height, hint.height())
        self.setMinimumHeight(y + line_height + 12)


class TextPanel(QScrollArea):
    def __init__(self) -> None:
        super().__init__()
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.holder = QWidget()
        layout = QVBoxLayout(self.holder)
        layout.setContentsMargins(12, 12, 12, 12)
        self.placeholder = QLabel("Text shows up here after a region settles.")
        self.placeholder.setWordWrap(True)
        self.placeholder.setStyleSheet("color: #8b8d93;")
        self.plain = QLabel()
        self.plain.setWordWrap(True)
        self.plain.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.plain.setFont(QFont("Yu Gothic UI", 14))
        self.plain.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.plain.hide()
        self.flow = _Flow()
        self.flow.hide()
        layout.addWidget(self.placeholder)
        layout.addWidget(self.plain)
        layout.addWidget(self.flow)
        layout.addStretch(1)
        self.setWidget(self.holder)

    def show_plain(self, text: str) -> None:
        self.flow.hide()
        self.plain.setText(text)
        has_text = bool(text.strip())
        self.plain.setVisible(has_text)
        self.placeholder.setVisible(not has_text)
        self._fit_plain()

    def show_ruby(self, tokens: list[Token]) -> None:
        self.plain.hide()
        has_text = any(not token.break_line and token.surface for token in tokens)
        self.placeholder.setVisible(not has_text)
        self.flow.setVisible(has_text)
        if has_text:
            self._fit_flow()
            self.flow.set_tokens(tokens)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._fit_plain()
        if self.flow.isVisible():
            self._fit_flow()

    def _fit_plain(self) -> None:
        width = max(40, self.viewport().width() - 28)
        self.plain.setFixedWidth(width)

    def _fit_flow(self) -> None:
        self.flow.setFixedWidth(max(40, self.viewport().width() - 28))
