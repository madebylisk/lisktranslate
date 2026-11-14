"""Always-on-top rectangle the user drags over on-screen text."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QMenu, QWidget

from lisktranslate import win32

MIN_SIZE = 48
_GRIP = 10
_CURSORS = {
    "move": Qt.CursorShape.SizeAllCursor,
    "l": Qt.CursorShape.SizeHorCursor,
    "r": Qt.CursorShape.SizeHorCursor,
    "t": Qt.CursorShape.SizeVerCursor,
    "b": Qt.CursorShape.SizeVerCursor,
    "tl": Qt.CursorShape.SizeFDiagCursor,
    "br": Qt.CursorShape.SizeFDiagCursor,
    "tr": Qt.CursorShape.SizeBDiagCursor,
    "bl": Qt.CursorShape.SizeBDiagCursor,
}
_FLAGS = (
    Qt.WindowType.FramelessWindowHint
    | Qt.WindowType.WindowStaysOnTopHint
    | Qt.WindowType.Tool
    | Qt.WindowType.WindowDoesNotAcceptFocus
)


class RegionFrame(QWidget):
    remove_requested = Signal(object)
    drag_finished = Signal(object)

    def __init__(self, region_id: int, index: int) -> None:
        super().__init__(None, _FLAGS)
        self.region_id = region_id
        self.index = index
        self.rel: tuple[int, int, int, int] | None = None
        self.dragging = False
        self._mode = "move"
        self._press = QPoint()
        self._start = QRect()
        self._click_through = False
        self._hidden = False
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        self.setMinimumSize(MIN_SIZE, MIN_SIZE)
        self.resize(520, 150)

    def set_index(self, index: int) -> None:
        self.index = index
        self.update()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        win32.exclude_from_capture(int(self.winId()))
        self._apply_mouse()

    def set_click_through(self, enabled: bool) -> None:
        self._click_through = enabled
        self._apply_mouse()
        self.update()

    def set_frame_hidden(self, hidden: bool) -> None:
        self._hidden = hidden
        self.setWindowOpacity(0.0 if hidden else 1.0)
        self.update()

    def ensure_input_mode(self) -> None:
        self._apply_mouse()

    def _apply_mouse(self) -> None:
        if not self.isVisible():
            return
        win32.set_mouse_transparent(int(self.winId()), self._click_through or self._hidden)

    def _hit(self, pos: QPoint) -> str:
        left = pos.x() <= _GRIP
        right = pos.x() >= self.width() - _GRIP
        top = pos.y() <= _GRIP
        bottom = pos.y() >= self.height() - _GRIP
        if top and left:
            return "tl"
        if top and right:
            return "tr"
        if bottom and left:
            return "bl"
        if bottom and right:
            return "br"
        if left:
            return "l"
        if right:
            return "r"
        if top:
            return "t"
        if bottom:
            return "b"
        return "move"

    def paintEvent(self, _event) -> None:
        if self._hidden:
            return
        painter = QPainter(self)
        color = QColor("#6ee7b7")
        if self._click_through:
            color.setAlpha(120)
        painter.setPen(QPen(color, 2))
        painter.setBrush(QColor(110, 231, 183, 24))
        painter.drawRect(self.rect().adjusted(1, 1, -2, -2))
        painter.drawText(10, 18, str(self.index))

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.RightButton:
            menu = QMenu(self)
            remove = menu.addAction("Remove region")
            if menu.exec(event.globalPosition().toPoint()) == remove:
                self.remove_requested.emit(self)
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._mode = self._hit(event.position().toPoint())
        self._press = event.globalPosition().toPoint()
        self._start = self.geometry()
        self.dragging = True

    def mouseMoveEvent(self, event) -> None:
        if not self.dragging:
            self.setCursor(_CURSORS[self._hit(event.position().toPoint())])
            return
        delta = event.globalPosition().toPoint() - self._press
        self.setGeometry(self._resized(self._mode, self._start, delta))

    def mouseReleaseEvent(self, event) -> None:
        if not self.dragging:
            return
        self.dragging = False
        self.drag_finished.emit(self)

    def _resized(self, mode: str, start: QRect, delta: QPoint) -> QRect:
        x, y, width, height = start.x(), start.y(), start.width(), start.height()
        dx, dy = delta.x(), delta.y()
        if mode == "move":
            return QRect(x + dx, y + dy, width, height)
        left = "l" in mode
        right = "r" in mode
        top = "t" in mode
        bottom = "b" in mode
        if left:
            x += dx
            width -= dx
        if right:
            width += dx
        if top:
            y += dy
            height -= dy
        if bottom:
            height += dy
        if width < MIN_SIZE:
            if left:
                x -= MIN_SIZE - width
            width = MIN_SIZE
        if height < MIN_SIZE:
            if top:
                y -= MIN_SIZE - height
            height = MIN_SIZE
        return QRect(x, y, width, height)
