"""Map Qt screen rectangles to physical pixels and crop them."""

from __future__ import annotations

from PIL import Image
from PySide6.QtCore import QPoint, QRect
from PySide6.QtGui import QGuiApplication, QScreen

from lisktranslate import win32
from lisktranslate.detect import is_blank

Monitor = tuple[str, int, int, int, int]


def map_point(
    value_x: float,
    value_y: float,
    screen: tuple[float, float, float, float],
    monitor: tuple[int, int, int, int],
) -> tuple[int, int]:
    sx, sy, sw, sh = screen
    left, top, right, bottom = monitor
    fx = 0.0 if sw == 0 else (value_x - sx) / sw
    fy = 0.0 if sh == 0 else (value_y - sy) / sh
    return (
        int(round(left + fx * (right - left))),
        int(round(top + fy * (bottom - top))),
    )


def _screen_at(point: QPoint) -> QScreen:
    screen = QGuiApplication.screenAt(point)
    return screen or QGuiApplication.primaryScreen()


def _match_screen(name: str) -> QScreen | None:
    wanted = name.lower()
    for screen in QGuiApplication.screens():
        if screen.name().lower() == wanted:
            return screen
    return None


def _containing(x: int, y: int, monitors: list[Monitor]) -> Monitor | None:
    for monitor in monitors:
        _, left, top, right, bottom = monitor
        if left <= x < right and top <= y < bottom:
            return monitor
    for monitor in monitors:
        _, left, top, right, bottom = monitor
        if left <= x <= right and top <= y <= bottom:
            return monitor
    return None


def dip_to_physical(point: QPoint) -> tuple[int, int]:
    screen = _screen_at(point)
    monitors = win32.enumerate_monitors()
    for name, left, top, right, bottom in monitors:
        if _match_screen(name) is screen:
            geo = screen.geometry()
            return map_point(
                point.x(),
                point.y(),
                (geo.x(), geo.y(), geo.width(), geo.height()),
                (left, top, right, bottom),
            )
    ratio = screen.devicePixelRatio()
    return int(round(point.x() * ratio)), int(round(point.y() * ratio))


def physical_to_dip(x: int, y: int) -> QPoint:
    monitors = win32.enumerate_monitors()
    monitor = _containing(x, y, monitors)
    if monitor is not None:
        name, left, top, right, bottom = monitor
        screen = _match_screen(name)
        if screen is not None and right > left and bottom > top:
            geo = screen.geometry()
            fx = (x - left) / (right - left)
            fy = (y - top) / (bottom - top)
            return QPoint(
                int(round(geo.x() + fx * geo.width())),
                int(round(geo.y() + fy * geo.height())),
            )
    screen = QGuiApplication.primaryScreen()
    ratio = screen.devicePixelRatio() or 1
    return QPoint(int(round(x / ratio)), int(round(y / ratio)))


def dip_rect_to_physical(rect: QRect) -> tuple[int, int, int, int]:
    x1, y1 = dip_to_physical(rect.topLeft())
    x2, y2 = dip_to_physical(QPoint(rect.x() + rect.width(), rect.y() + rect.height()))
    return x1, y1, max(1, x2 - x1), max(1, y2 - y1)


def physical_rect_to_dip(x: int, y: int, width: int, height: int) -> QRect:
    origin = physical_to_dip(x, y)
    corner = physical_to_dip(x + width, y + height)
    return QRect(origin.x(), origin.y(), max(1, corner.x() - origin.x()), max(1, corner.y() - origin.y()))


def grab_screen(rect: QRect) -> Image.Image:
    x, y, width, height = dip_rect_to_physical(rect)
    return win32.capture_screen(x, y, width, height)


def grab_window(hwnd: int, rel: tuple[int, int, int, int]) -> Image.Image | None:
    """Crop a bound window. None when PrintWindow returns a blank frame."""
    if not win32.is_window(hwnd) or win32.is_minimized(hwnd):
        return None
    try:
        image = win32.capture_window(hwnd)
    except OSError:
        return None
    x, y, width, height = rel
    x1 = max(0, x)
    y1 = max(0, y)
    x2 = min(image.width, x + width)
    y2 = min(image.height, y + height)
    if x2 <= x1 or y2 <= y1:
        return None
    crop = image.crop((x1, y1, x2, y2))
    if is_blank(crop):
        return None
    return crop
