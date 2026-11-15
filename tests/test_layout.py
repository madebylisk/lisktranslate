import unittest

from lisktranslate.layout import assemble, guess_vertical, split_speaker


class LayoutTests(unittest.TestCase):
    def test_horizontal_reading_order_and_rows(self):
        text = assemble(
            [
                ("B", (60, 0, 100, 20)),
                ("A", (0, 0, 40, 20)),
                ("C", (0, 40, 40, 60)),
            ]
        )
        self.assertEqual(text, "A B\nC")

    def test_japanese_lines_keep_a_break_when_they_are_apart(self):
        text = assemble(
            [
                ("今日は", (0, 0, 80, 20)),
                ("いい", (80, 0, 130, 20)),
                ("天気", (0, 30, 50, 50)),
            ]
        )
        self.assertEqual(text, "今日はいい\n天気")

    def test_close_wrapped_lines_join_into_one_sentence(self):
        text = assemble(
            [
                ("今日は", (0, 0, 80, 20)),
                ("いい", (80, 0, 130, 20)),
                ("天気", (0, 22, 50, 42)),
            ]
        )
        self.assertEqual(text, "今日はいい天気")

    def test_nameplate_stays_out_of_the_sentence(self):
        text = assemble(
            [
                ("街人", (12, 4, 78, 28)),
                ("よう、外は寒かっただろ！", (12, 52, 540, 80)),
                ("温かいスープはどうだい？", (12, 100, 380, 128)),
            ]
        )
        speaker, body = split_speaker(text)
        self.assertEqual(speaker, "街人")
        self.assertEqual(body, "よう、外は寒かっただろ！\n温かいスープはどうだい？")

    def test_hiragana_and_tight_wraps_stay_in_the_sentence(self):
        exclamation = assemble(
            [
                ("えっ", (10, 0, 60, 24)),
                ("本当に行くの？", (10, 48, 300, 76)),
            ]
        )
        self.assertEqual(split_speaker(exclamation)[0], "")
        self.assertIn("えっ", exclamation)
        wrapped = assemble(
            [
                ("今日", (0, 0, 48, 20)),
                ("はいい天気ですね。", (0, 22, 240, 42)),
            ]
        )
        self.assertEqual(split_speaker(wrapped)[0], "")
        self.assertIn("今日", wrapped)

    def test_vertical_columns_read_right_to_left(self):
        boxes = [(100, 0, 120, 200), (70, 0, 90, 200)]
        self.assertTrue(guess_vertical(boxes))
        text = assemble([("右", boxes[0]), ("左", boxes[1])])
        self.assertEqual(text, "右\n左")


if __name__ == "__main__":
    unittest.main()
