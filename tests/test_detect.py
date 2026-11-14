import unittest

from PIL import Image

from lisktranslate.capture import map_point
from lisktranslate.detect import FrameTracker, levenshtein, ssim, thumbnail


class DetectTests(unittest.TestCase):
    def test_identical_frames_score_one(self):
        image = thumbnail(Image.new("RGB", (80, 40), "white"))
        self.assertAlmostEqual(ssim(image, image), 1.0)

    def test_edit_distance(self):
        self.assertEqual(levenshtein("kitten", "sitting"), 3)
        self.assertEqual(levenshtein("こんにちは", "こんにちわ"), 1)

    def test_small_ocr_flicker_does_not_replace_text(self):
        tracker = FrameTracker()
        self.assertTrue(tracker.accept_text("こんにちは"))
        self.assertFalse(tracker.accept_text("こんにちわ"))
        self.assertEqual(tracker.text, "こんにちは")
        self.assertTrue(tracker.accept_text("こんにちは。元気？"))

    def test_unchanged_image_is_not_sent_twice(self):
        tracker = FrameTracker()
        image = Image.new("RGB", (120, 60), "white")
        self.assertTrue(tracker.wants_ocr(image))
        self.assertFalse(tracker.wants_ocr(image.copy()))

    def test_dip_fraction_maps_onto_the_monitor(self):
        self.assertEqual(
            map_point(100, 200, (0, 0, 1920, 1080), (0, 0, 3840, 2160)),
            (200, 400),
        )


if __name__ == "__main__":
    unittest.main()
