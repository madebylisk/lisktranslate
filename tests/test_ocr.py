import unittest
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from lisktranslate import win32
from lisktranslate.ocr_engine import OcrService, prepare_image, snipping_tool_dir


def _font():
    for path in (
        Path(r"C:\Windows\Fonts\YuGothM.ttc"),
        Path(r"C:\Windows\Fonts\meiryo.ttc"),
        Path(r"C:\Windows\Fonts\msgothic.ttc"),
    ):
        if path.is_file():
            return ImageFont.truetype(str(path), 48)
    raise unittest.SkipTest("No Japanese font found")


class OcrTests(unittest.TestCase):
    def test_small_images_are_padded_to_the_engine_minimum(self):
        image = prepare_image(Image.new("RGB", (10, 80), "white"))
        self.assertGreaterEqual(min(image.size), 50)

    def test_screen_capture_returns_the_requested_size(self):
        image = win32.capture_screen(0, 0, 32, 24)
        self.assertEqual(image.size, (32, 24))

    @unittest.skipUnless(snipping_tool_dir(), "Snipping Tool OCR is not installed")
    def test_oneocr_reads_a_japanese_sentence(self):
        image = Image.new("RGB", (980, 180), "white")
        ImageDraw.Draw(image).text((30, 50), "今日はいい天気ですね。", font=_font(), fill="black")
        service = OcrService()
        self.assertEqual(service.engine_name, "OneOCR")
        text = service.recognize(image)
        self.assertIn("天気", text)
        self.assertIn("今日", text)


if __name__ == "__main__":
    unittest.main()
