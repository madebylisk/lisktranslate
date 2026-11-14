"""Decide when a captured region is stable enough to OCR again."""

from __future__ import annotations

from PIL import Image

STABLE_SIMILARITY = 0.5
UNCHANGED_SIMILARITY = 0.95
TEXT_DISTANCE = 3
_THUMB = (64, 64)


def thumbnail(image: Image.Image) -> Image.Image:
    return image.convert("L").resize(_THUMB, Image.Resampling.BOX)


def ssim(a: Image.Image, b: Image.Image) -> float:
    """Global SSIM of two same-sized grayscale images. 1 means identical."""
    import numpy as np

    if a.size != b.size:
        return 0.0
    x = np.asarray(a, dtype=np.float64)
    y = np.asarray(b, dtype=np.float64)
    c1 = (0.01 * 255) ** 2
    c2 = (0.03 * 255) ** 2
    mx = float(x.mean())
    my = float(y.mean())
    vx = float(x.var())
    vy = float(y.var())
    cov = float(((x - mx) * (y - my)).mean())
    score = ((2 * mx * my + c1) * (2 * cov + c2)) / ((mx * mx + my * my + c1) * (vx + vy + c2))
    if score < 0:
        return 0.0
    if score > 1:
        return 1.0
    return score


def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    if len(a) < len(b):
        a, b = b, a
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(
                min(
                    current[j - 1] + 1,
                    previous[j] + 1,
                    previous[j - 1] + (ca != cb),
                )
            )
        previous = current
    return previous[-1]


def is_blank(image: Image.Image) -> bool:
    """True for a failed capture that came back nearly black and flat."""
    import numpy as np

    sample = np.asarray(thumbnail(image), dtype=np.float32)
    return float(sample.mean()) < 8 and float(sample.std()) < 3


class FrameTracker:
    """Per-region memory of the last frame and the last text we showed."""

    def __init__(self) -> None:
        self.text = ""
        self._last: Image.Image | None = None
        self._ocr: Image.Image | None = None
        self._size: tuple[int, int] | None = None

    def reset_image(self) -> None:
        self._last = None
        self._ocr = None
        self._size = None

    def wants_ocr(self, image: Image.Image) -> bool:
        thumb = thumbnail(image)
        if self._size != image.size or self._last is None:
            self._size = image.size
            self._last = thumb
            self._ocr = thumb
            return True
        similarity = ssim(self._last, thumb)
        self._last = thumb
        if similarity < STABLE_SIMILARITY:
            return False
        if self._ocr is not None and ssim(self._ocr, thumb) > UNCHANGED_SIMILARITY:
            return False
        self._ocr = thumb
        return True

    def retry_next(self) -> None:
        self._ocr = None

    def accept_text(self, text: str) -> bool:
        if not text:
            return False
        if self.text and levenshtein(self.text, text) < TEXT_DISTANCE:
            return False
        self.text = text
        return True
