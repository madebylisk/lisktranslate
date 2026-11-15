"""Text panel. Furigana is drawn above kanji; Qt's text widget has no ruby tags."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import QFrame, QLabel, QScrollArea, QSizePolicy, QVBoxLayout, QWidget

from lisktranslate.furigana import Token


class RubyWord(QWidget):
    def __init__(
        self,
        surface: str,
        reading: str | None,
        gap_before: int = 0,
        show_reading_row: bool = True,
        muted: bool = False,
        reading_size: int = 8,
        surface_size: int = 15,
        pad_right: int = 3,
    ) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(gap_before + 1, 0, pad_right, 0)
        layout.setSpacing(0)
        if show_reading_row:
            self.reading = QLabel(reading or " ")
            self.reading.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom)
            self.reading.setFont(QFont("Yu Gothic UI", reading_size))
            self.reading.setStyleSheet("color: #a7f3d0;" if reading else "color: transparent;")
            self.reading.setFixedHeight(QFontMetrics(self.reading.font()).height())
            layout.addWidget(self.reading)
        self.surface = QLabel(surface)
        self.surface.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.surface.setFont(QFont("Yu Gothic UI", surface_size))
        self.surface.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.surface.setStyleSheet("color: #b9babf;" if muted else "color: #ececec;")
        layout.addWidget(self.surface)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)


class _Flow(QWidget):
    def __init__(self, tail: int = 12) -> None:
        super().__init__()
        self._items: list[QWidget | None] = []
        self._tail = tail
        self._reading_size = 8
        self._surface_size = 15
        self._pad_right = 3

    def set_tokens(
        self,
        tokens: list[Token],
        show_readings: bool = True,
        reading_size: int = 8,
        surface_size: int = 15,
        pad_right: int = 3,
    ) -> None:
        self._reading_size = reading_size
        self._surface_size = surface_size
        self._pad_right = pad_right
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
            word = RubyWord(
                token.surface,
                token.reading if show_readings else None,
                token.gap_before,
                show_reading_row=show_readings,
                muted=token.muted,
                reading_size=self._reading_size,
                surface_size=self._surface_size,
                pad_right=self._pad_right,
            )
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
        self.setMinimumHeight(y + line_height + self._tail)


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
        self._flows: list[_Flow] = []
        self._wrap_labels: list[QLabel] = []
        self.sections = QVBoxLayout()
        self.sections.setSpacing(16)
        layout.addWidget(self.placeholder)
        layout.addLayout(self.sections)
        layout.addStretch(1)
        self.setWidget(self.holder)

    def show_sections(self, sections: list[tuple[str, str, list[Token] | None, str, bool]]) -> None:
        self._clear_sections()
        self.placeholder.setVisible(not sections)
        width = self._content_width()
        for title, japanese, tokens, english, show_readings in sections:
            block = QWidget()
            block_layout = QVBoxLayout(block)
            block_layout.setContentsMargins(0, 0, 0, 0)
            block_layout.setSpacing(6)
            if title:
                heading = QLabel(title)
                heading.setFont(QFont("Yu Gothic UI", 9))
                heading.setStyleSheet("color: #a1a1aa;")
                block_layout.addWidget(heading)
            if tokens is not None:
                flow = _Flow()
                flow.setFixedWidth(width)
                flow.set_tokens(tokens, show_readings=show_readings)
                self._flows.append(flow)
                block_layout.addWidget(flow)
            else:
                source = self._wrapping_label(japanese, QFont("Yu Gothic UI", 14), "#ececec")
                source.setFixedWidth(width)
                block_layout.addWidget(source)
            if english:
                translation = self._wrapping_label(english, QFont("Segoe UI", 13), "#d6e4dc")
                translation.setFixedWidth(width)
                block_layout.addWidget(translation)
            self.sections.addWidget(block)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        width = self._content_width()
        for label in self._wrap_labels:
            label.setFixedWidth(width)
        for flow in self._flows:
            flow.setFixedWidth(width)

    def _content_width(self) -> int:
        return max(40, self.viewport().width() - 28)

    def _wrapping_label(self, text: str, font: QFont, color: str) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setFont(font)
        label.setStyleSheet(f"color: {color};")
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._wrap_labels.append(label)
        return label

    def _clear_sections(self) -> None:
        while self.sections.count():
            item = self.sections.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self._flows.clear()
        self._wrap_labels.clear()
