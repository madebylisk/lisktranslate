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
        self.assertGreater(gaps["です"], 0)
        self.assertEqual(gaps["ね"], 0)
        self.assertEqual(gaps.get("。", 0), 0)
        self.assertEqual(gaps.get("」", 0), 0)
        self.assertTrue(muted["は"])
        self.assertTrue(muted["です"])
        self.assertTrue(muted["ね"])
        self.assertFalse(muted["今日"])
        self.assertFalse(muted["天気"])

    def test_particle_chains_stay_together(self):
        tokens = Furigana().tokens("好きなのに行けないんだよ", spacing=True)
        self.assertEqual(
            [(token.surface, token.gap_before > 0) for token in tokens],
            [
                ("好き", False),
                ("な", True),
                ("の", False),
                ("に", False),
                ("行け", True),
                ("ない", True),
                ("ん", False),
                ("だ", False),
                ("よ", False),
            ],
        )
        named = Furigana().tokens("田中さんに会う", spacing=True)
        self.assertEqual(
            [(token.surface, token.gap_before > 0) for token in named],
            [("田中", False), ("さん", True), ("に", False), ("会う", True)],
        )

    def test_polite_masu_stays_on_the_verb(self):
        tokens = Furigana().tokens("お願いいたします", spacing=True)
        self.assertEqual(
            [(token.surface, token.gap_before > 0) for token in tokens],
            [("お", False), ("願い", False), ("いたし", True), ("ます", False)],
        )
        polite = Furigana().tokens("いたしませんでした", spacing=True)
        self.assertEqual([token.gap_before for token in polite], [0, 0, 0, 0, 0])
        weather = Furigana().tokens("天気ですね", spacing=True)
        gaps = {token.surface: token.gap_before for token in weather}
        self.assertGreater(gaps["です"], 0)
        self.assertEqual(gaps["ね"], 0)


if __name__ == "__main__":
    unittest.main()
