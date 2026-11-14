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


if __name__ == "__main__":
    unittest.main()
