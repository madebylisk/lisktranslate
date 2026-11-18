"""Text panel. Furigana is drawn above kanji; Qt's text widget has no ruby tags."""

from __future__ import annotations

from typing import NamedTuple

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import QFrame, QLabel, QScrollArea, QSizePolicy, QVBoxLayout, QWidget

from lisktranslate.furigana import Token


class TextStyle(NamedTuple):
    name: str
    reading: int
    surface: int
    english: int
    japanese: int
    heading: int


# Small is the original size of the recognized text and its translation.
TEXT_STYLES = (
    TextStyle("Small", 8, 15, 13, 14, 9),
    TextStyle("Medium", 10, 19, 17, 18, 11),
    TextStyle("Large", 13, 24, 21, 22, 13),
    TextStyle("Extra large", 16, 30, 26, 28, 16),
)


def text_style(saved) -> TextStyle:
    if isinstance(saved, str):
        for style in TEXT_STYLES:
            if style.name == saved:
                return style
    return TEXT_STYLES[0]


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
        heading_size: int = 9,
        gap_scale: float = 1,
    ) -> None:
        self._reading_size = reading_size
        self._surface_size = surface_size
        self._pad_right = pad_right
        self._heading_size = heading_size
        self._gap_scale = gap_scale
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
                label.setFont(QFont("Yu Gothic UI", self._heading_size))
                label.setStyleSheet("color: #a1a1aa;")
                label.setParent(self)
                self._items.append(label)
                self._items.append(None)
                continue
            gap = token.gap_before
            if gap and self._gap_scale != 1:
                gap = round(gap * self._gap_scale)
            word = RubyWord(
                token.surface,
                token.reading if show_readings else None,
                gap,
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
        self._style = TEXT_STYLES[0]
        self._flows: list[_Flow] = []
        self._wrap_labels: list[QLabel] = []
        self.sections = QVBoxLayout()
        self.sections.setSpacing(16)
        layout.addWidget(self.placeholder)
        layout.addLayout(self.sections)
        layout.addStretch(1)
        self.setWidget(self.holder)

    def set_style(self, style: TextStyle) -> None:
        self._style = style

    def show_sections(self, sections: list[tuple[str, str, list[Token] | None, str, bool]]) -> None:
        self._clear_sections()
        self.placeholder.setVisible(not sections)
        width = self._content_width()
        style = self._style
        for title, japanese, tokens, english, show_readings in sections:
            block = QWidget()
            block_layout = QVBoxLayout(block)
            block_layout.setContentsMargins(0, 0, 0, 0)
            block_layout.setSpacing(max(6, round(6 * style.surface / 15)))
            if title:
                heading = QLabel(title)
                heading.setFont(QFont("Yu Gothic UI", style.heading))
                heading.setStyleSheet("color: #a1a1aa;")
                block_layout.addWidget(heading)
            if tokens is not None:
                flow = _Flow()
                flow.setFixedWidth(width)
                flow.set_tokens(
                    tokens,
                    show_readings=show_readings,
                    reading_size=style.reading,
                    surface_size=style.surface,
                    pad_right=max(3, round(3 * style.surface / 15)),
                    heading_size=style.heading,
                    gap_scale=style.surface / 15,
                )
                self._flows.append(flow)
                block_layout.addWidget(flow)
            else:
                source = self._wrapping_label(japanese, QFont("Yu Gothic UI", style.japanese), "#ececec")
                source.setFixedWidth(width)
                block_layout.addWidget(source)
            if english:
                translation = self._wrapping_label(english, QFont("Segoe UI", style.english), "#d6e4dc")
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
