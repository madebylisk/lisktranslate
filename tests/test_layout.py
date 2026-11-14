import unittest

from lisktranslate.layout import assemble, guess_vertical


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

    def test_vertical_columns_read_right_to_left(self):
        boxes = [(100, 0, 120, 200), (70, 0, 90, 200)]
        self.assertTrue(guess_vertical(boxes))
        text = assemble([("右", boxes[0]), ("左", boxes[1])])
        self.assertEqual(text, "右\n左")


if __name__ == "__main__":
    unittest.main()
