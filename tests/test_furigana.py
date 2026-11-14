import unittest

from lisktranslate.furigana import Furigana, kata_to_hira


class FuriganaTests(unittest.TestCase):
    def test_katakana_converts_to_hiragana(self):
        self.assertEqual(kata_to_hira("キョウ"), "きょう")

    def test_kanji_get_readings_and_kana_do_not(self):
        tokens = Furigana().tokens("今日はいい天気です")
        self.assertEqual("".join(token.surface for token in tokens), "今日はいい天気です")
        readings = {token.surface: token.reading for token in tokens}
        self.assertEqual(readings["今日"], "きょう")
        self.assertEqual(readings["天気"], "てんき")
        self.assertIsNone(readings["は"])
        self.assertIsNone(readings["です"])

    def test_spacing_separates_words_and_particles(self):
        plain = Furigana().tokens("「今日はいい天気ですね。」")
        self.assertTrue(all(token.gap_before == 0 and not token.muted for token in plain))
        spaced = Furigana().tokens("「今日はいい天気ですね。」", spacing=True)
        gaps = {token.surface: token.gap_before for token in spaced}
        muted = {token.surface: token.muted for token in spaced}
        self.assertEqual("".join(token.surface for token in spaced), "「今日はいい天気ですね。」")
        self.assertEqual(gaps["「"], 0)
        self.assertEqual(gaps["今日"], 0)
        self.assertGreater(gaps["は"], 0)
        self.assertGreater(gaps["いい"], 0)
        self.assertGreater(gaps["天気"], 0)
        self.assertGreater(gaps["です"], gaps["天気"])
        self.assertEqual(gaps.get("。", 0), 0)
        self.assertEqual(gaps.get("」", 0), 0)
        self.assertTrue(muted["は"])
        self.assertTrue(muted["です"])
        self.assertFalse(muted["今日"])
        self.assertFalse(muted["天気"])


if __name__ == "__main__":
    unittest.main()
