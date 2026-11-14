"""Win32 capture and window lookup. Coordinates here are physical pixels."""

from __future__ import annotations

import ctypes
from ctypes import wintypes

from PIL import Image

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

SRCCOPY = 0x00CC0020
PW_RENDERFULLCONTENT = 2
GA_ROOT = 2
GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WDA_EXCLUDEFROMCAPTURE = 0x00000011
DIB_RGB_COLORS = 0

user32.SetWindowDisplayAffinity.argtypes = [wintypes.HWND, wintypes.DWORD]
user32.SetWindowDisplayAffinity.restype = wintypes.BOOL
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetWindowRect.restype = wintypes.BOOL
user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsWindow.restype = wintypes.BOOL
user32.IsIconic.argtypes = [wintypes.HWND]
user32.IsIconic.restype = wintypes.BOOL
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetAncestor.restype = wintypes.HWND
user32.WindowFromPoint.argtypes = [wintypes.POINT]
user32.WindowFromPoint.restype = wintypes.HWND
user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
user32.GetCursorPos.restype = wintypes.BOOL
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL
user32.GetDC.argtypes = [wintypes.HWND]
user32.GetDC.restype = wintypes.HDC
user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
user32.ReleaseDC.restype = ctypes.c_int
user32.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
user32.PrintWindow.restype = wintypes.BOOL
user32.EnumWindows.argtypes = [ctypes.c_void_p, wintypes.LPARAM]
user32.EnumWindows.restype = wintypes.BOOL

gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi32.CreateCompatibleDC.restype = wintypes.HDC
gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
gdi32.SelectObject.restype = wintypes.HGDIOBJ
gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
gdi32.DeleteObject.restype = wintypes.BOOL
gdi32.DeleteDC.argtypes = [wintypes.HDC]
gdi32.DeleteDC.restype = wintypes.BOOL
gdi32.BitBlt.argtypes = [
    wintypes.HDC,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.HDC,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.DWORD,
]
gdi32.BitBlt.restype = wintypes.BOOL
gdi32.GetDIBits.argtypes = [
    wintypes.HDC,
    wintypes.HBITMAP,
    wintypes.UINT,
    wintypes.UINT,
    ctypes.c_void_p,
    ctypes.c_void_p,
    wintypes.UINT,
]
gdi32.GetDIBits.restype = ctypes.c_int

user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.EnumDisplayMonitors.argtypes = [
    wintypes.HDC,
    ctypes.c_void_p,
    ctypes.c_void_p,
    wintypes.LPARAM,
]
user32.EnumDisplayMonitors.restype = wintypes.BOOL
user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.c_void_p]
user32.GetMonitorInfoW.restype = wintypes.BOOL


class MONITORINFOEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT),
        ("dwFlags", wintypes.DWORD),
        ("szDevice", ctypes.c_wchar * 32),
    ]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [
        ("bmiHeader", BITMAPINFOHEADER),
        ("bmiColors", wintypes.DWORD * 3),
    ]


def exclude_from_capture(hwnd: int) -> None:
    user32.SetWindowDisplayAffinity(wintypes.HWND(hwnd), WDA_EXCLUDEFROMCAPTURE)


def is_window(hwnd: int) -> bool:
    return bool(hwnd) and bool(user32.IsWindow(wintypes.HWND(hwnd)))


def is_minimized(hwnd: int) -> bool:
    return bool(user32.IsIconic(wintypes.HWND(hwnd)))


def window_title(hwnd: int) -> str:
    length = user32.GetWindowTextLengthW(wintypes.HWND(hwnd))
    if length <= 0:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(wintypes.HWND(hwnd), buffer, length + 1)
    return buffer.value


def window_rect(hwnd: int) -> tuple[int, int, int, int]:
    rect = wintypes.RECT()
    if not user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(rect)):
        raise OSError("GetWindowRect failed")
    return rect.left, rect.top, rect.right, rect.bottom


def root_at_cursor() -> int:
    point = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(point))
    hwnd = user32.WindowFromPoint(point)
    if not hwnd:
        return 0
    root = user32.GetAncestor(hwnd, GA_ROOT)
    return int(root or hwnd)


def key_down(vk: int) -> bool:
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


def find_window_by_title(title: str) -> int:
    if not title:
        return 0
    found: list[int] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def visit(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        if window_title(int(hwnd)) == title:
            found.append(int(hwnd))
            return False
        return True

    user32.EnumWindows(visit, 0)
    return found[0] if found else 0


def _image_from_bitmap(dc, bitmap, width: int, height: int) -> Image.Image:
    info = BITMAPINFO()
    info.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    info.bmiHeader.biWidth = width
    info.bmiHeader.biHeight = -height
    info.bmiHeader.biPlanes = 1
    info.bmiHeader.biBitCount = 32
    info.bmiHeader.biCompression = 0
    buffer = (ctypes.c_ubyte * (width * height * 4))()
    rows = gdi32.GetDIBits(
        dc, bitmap, 0, height, buffer, ctypes.byref(info), DIB_RGB_COLORS
    )
    if rows == 0:
        raise OSError("GetDIBits failed")
    return Image.frombytes("RGB", (width, height), bytes(buffer), "raw", "BGRX", 0, 1)


def _bitmap_dc(width: int, height: int):
    screen = user32.GetDC(0)
    if not screen:
        raise OSError("GetDC failed")
    memory = gdi32.CreateCompatibleDC(screen)
    bitmap = gdi32.CreateCompatibleBitmap(screen, width, height)
    previous = gdi32.SelectObject(memory, bitmap)
    return screen, memory, bitmap, previous


def _release_bitmap(screen, memory, bitmap, previous) -> None:
    if previous:
        gdi32.SelectObject(memory, previous)
    if bitmap:
        gdi32.DeleteObject(bitmap)
    if memory:
        gdi32.DeleteDC(memory)
    if screen:
        user32.ReleaseDC(0, screen)


def capture_screen(x: int, y: int, width: int, height: int) -> Image.Image:
    if width < 1 or height < 1:
        raise ValueError("empty capture")
    screen, memory, bitmap, previous = _bitmap_dc(width, height)
    try:
        if not gdi32.BitBlt(memory, 0, 0, width, height, screen, x, y, SRCCOPY):
            raise OSError("BitBlt failed")
        return _image_from_bitmap(memory, bitmap, width, height)
    finally:
        _release_bitmap(screen, memory, bitmap, previous)


def capture_window(hwnd: int) -> Image.Image:
    left, top, right, bottom = window_rect(hwnd)
    width = right - left
    height = bottom - top
    if width < 1 or height < 1:
        raise OSError("window has no pixels")
    screen, memory, bitmap, previous = _bitmap_dc(width, height)
    try:
        if not user32.PrintWindow(wintypes.HWND(hwnd), memory, PW_RENDERFULLCONTENT):
            raise OSError("PrintWindow failed")
        return _image_from_bitmap(memory, bitmap, width, height)
    finally:
        _release_bitmap(screen, memory, bitmap, previous)


def enumerate_monitors() -> list[tuple[str, int, int, int, int]]:
    monitors: list[tuple[str, int, int, int, int]] = []

    @ctypes.WINFUNCTYPE(
        wintypes.BOOL,
        wintypes.HMONITOR,
        wintypes.HDC,
        ctypes.POINTER(wintypes.RECT),
        wintypes.LPARAM,
    )
    def visit(monitor, _hdc, _rect, _data):
        info = MONITORINFOEXW()
        info.cbSize = ctypes.sizeof(MONITORINFOEXW)
        if user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            name = info.szDevice.split("\x00", 1)[0]
            rect = info.rcMonitor
            monitors.append((name, rect.left, rect.top, rect.right, rect.bottom))
        return True

    user32.EnumDisplayMonitors(None, None, visit, 0)
    return monitors


def set_mouse_transparent(hwnd: int, enabled: bool) -> None:
    style = user32.GetWindowLongPtrW(wintypes.HWND(hwnd), GWL_EXSTYLE)
    if enabled:
        style |= WS_EX_TRANSPARENT
    else:
        style &= ~WS_EX_TRANSPARENT
    user32.SetWindowLongPtrW(wintypes.HWND(hwnd), GWL_EXSTYLE, style)
