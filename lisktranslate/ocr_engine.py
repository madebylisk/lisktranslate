"""Load Snipping Tool OCR, and fall back to Windows.Media.Ocr."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from PIL import Image

from lisktranslate.layout import Box, assemble

_FILES = ("oneocr.dll", "oneocr.onemodel", "onnxruntime.dll")
_CREATE_NO_WINDOW = 0x08000000


def _cache_dir() -> Path:
    root = os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(root) / "lisktranslate" / "oneocr"


def snipping_tool_dir() -> Path | None:
    try:
        output = subprocess.check_output(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-AppxPackage -Name Microsoft.ScreenSketch).InstallLocation",
            ],
            text=True,
            creationflags=_CREATE_NO_WINDOW,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    path = Path(output.strip()) / "SnippingTool"
    if all((path / name).is_file() for name in _FILES):
        return path
    return None


def stage_oneocr(force: bool = False) -> Path:
    """Copy oneocr.dll and its model out of the WindowsApps package."""
    dest = _cache_dir()
    dest.mkdir(parents=True, exist_ok=True)
    ready = all((dest / name).is_file() for name in _FILES)
    if ready and not force:
        return dest
    source = snipping_tool_dir()
    if source is None:
        raise RuntimeError(
            "Snipping Tool OCR was not found. Install Snipping Tool from the Microsoft Store."
        )
    for name in _FILES:
        shutil.copyfile(source / name, dest / name)
    return dest


def prepare_image(image: Image.Image) -> Image.Image:
    """OneOCR rejects images smaller than 50px or larger than 10000px."""
    image = image.convert("RGB")
    width, height = image.size
    scale = 1.0
    if width < 50 or height < 50:
        scale = max(50 / max(width, 1), 50 / max(height, 1))
    longest = max(width, height) * scale
    if longest > 10000:
        scale *= 10000 / longest
    if abs(scale - 1.0) > 0.001:
        image = image.resize(
            (max(1, int(round(width * scale))), max(1, int(round(height * scale)))),
            Image.Resampling.LANCZOS,
        )
    width, height = image.size
    if width < 50 or height < 50:
        canvas = Image.new("RGB", (max(width, 50), max(height, 50)), "white")
        canvas.paste(image, (0, 0))
        return canvas
    return image


def _quad_box(box: dict) -> Box:
    xs = (box["x1"], box["x2"], box["x3"], box["x4"])
    ys = (box["y1"], box["y2"], box["y3"], box["y4"])
    return (min(xs), min(ys), max(xs), max(ys))


def _lines_from_oneocr(result: dict) -> list[tuple[str, Box]]:
    if result.get("error"):
        raise RuntimeError(str(result["error"]))
    lines: list[tuple[str, Box]] = []
    for line in result.get("lines") or []:
        text = (line.get("text") or "").strip()
        box = line.get("bounding_rect")
        if not text or not box:
            continue
        lines.append((text, _quad_box(box)))
    return lines


def _lines_from_winrt(image: Image.Image, lang: str = "ja") -> list[tuple[str, Box]]:
    import asyncio

    import winocr

    try:
        result = asyncio.run(winocr.to_coroutine(winocr.recognize_pil(image, lang)))
    except AssertionError as exc:
        raise RuntimeError(
            "Windows OCR has no Japanese language pack. "
            "OneOCR is unavailable, so install the Japanese OCR feature in Windows."
        ) from exc
    lines: list[tuple[str, Box]] = []
    for line in result.lines:
        text = (line.text or "").strip()
        if not text:
            continue
        rect = line.bounding_rect
        x = float(rect.x)
        y = float(rect.y)
        lines.append((text, (x, y, x + float(rect.width), y + float(rect.height))))
    return lines


class OcrService:
    """OneOCR first. Windows.Media.Ocr is used only if that DLL cannot run."""

    def __init__(self) -> None:
        self.engine_name = "unavailable"
        self._oneocr = None
        self._winrt = False
        self._error = "OCR is unavailable."
        self._load()

    def _load(self) -> None:
        oneocr_error = self._try_oneocr(force=False)
        if self._oneocr is not None:
            return
        oneocr_error = self._try_oneocr(force=True) or oneocr_error
        winrt_error = self._try_winrt()
        if self._winrt:
            self._error = oneocr_error or self._error
            return
        self._error = oneocr_error or winrt_error or self._error
        self.engine_name = "unavailable"

    def _try_oneocr(self, force: bool) -> str | None:
        try:
            import oneocr

            folder = stage_oneocr(force=force)
            os.add_dll_directory(str(folder))
            oneocr.CONFIG_DIR = str(folder)
            self._oneocr = oneocr.OcrEngine()
            self.engine_name = "OneOCR"
            self._error = ""
            return None
        except Exception as exc:
            self._oneocr = None
            return str(exc)

    def _try_winrt(self) -> str | None:
        try:
            import winocr  # noqa: F401

            self._winrt = True
            self.engine_name = "Windows OCR"
            return None
        except Exception as exc:
            self._winrt = False
            return str(exc)

    @property
    def available(self) -> bool:
        return self.engine_name != "unavailable"

    @property
    def status_line(self) -> str:
        if self.available:
            return self.engine_name
        return self._error

    def recognize(self, image: Image.Image) -> str:
        image = prepare_image(image)
        if self._oneocr is not None:
            return assemble(_lines_from_oneocr(self._oneocr.recognize_pil(image)))
        if self._winrt:
            return assemble(_lines_from_winrt(image))
        raise RuntimeError(self._error)
