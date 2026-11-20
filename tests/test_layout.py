import unittest

from lisktranslate.layout import assemble, guess_vertical, japanese_text, split_speaker


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

    def test_name_on_its_own_line_stays_out_of_the_sentence(self):
        text = (
            "老人\n"
            "業魔病は、変わらず広がり続けている。実際に\n"
            "治安が保たれているのは、限られた大都市部だけだ"
        )
        speaker, body = split_speaker(text)
        self.assertEqual(speaker, "老人")
        self.assertEqual(
            body,
            "業魔病は、変わらず広がり続けている。実際に\n"
            "治安が保たれているのは、限られた大都市部だけだ",
        )
        self.assertEqual(split_speaker("老人\nでも、業魔病は広がり続けている。")[0], "老人")

    def test_katakana_name_with_an_ellipsis_stays_out_of_the_sentence(self):
        dotted = "ロクロウ\n今の顔....ちょっとソレっぽかったぞ...."
        speaker, body = split_speaker(dotted)
        self.assertEqual(speaker, "ロクロウ")
        self.assertEqual(body, "今の顔....ちょっとソレっぽかったぞ....")
        for ellipsis in (
            "ロクロウ\n今の顔・・・ちょっとソレっぽかったぞ・・・",
            "ロクロウ\n今の顔……ちょっとソレっぽかったぞ……",
        ):
            speaker, body = split_speaker(ellipsis)
            self.assertEqual(speaker, "ロクロウ")
            self.assertNotIn("ロクロウ", body)
        self.assertEqual(split_speaker("ダメ\nそうは思わないと、さっきから思っていた。")[0], "")
        self.assertEqual(split_speaker("ソレ\nちょっと違って見えたぞ……")[0], "")

    def test_name_without_a_period_stays_out_of_the_sentence(self):
        text = "ロクロウ\nほう、なかなか雅な名前だな"
        speaker, body = split_speaker(text)
        self.assertEqual(speaker, "ロクロウ")
        self.assertEqual(body, "ほう、なかなか雅な名前だな")
        speaker, body = split_speaker("ロクロウほう、なかなか雅な名前だな")
        self.assertEqual(speaker, "ロクロウ")
        self.assertEqual(body, "ほう、なかなか雅な名前だな")
        self.assertEqual(split_speaker("ウソだな、それは違うと思う")[0], "")

    def test_stray_letter_on_the_nameplate_stays_out_of_the_sentence(self):
        text = "ベルベット M\n治療してもらった恩があるから\n斬りたくないとでもいうの？"
        speaker, body = split_speaker(text)
        self.assertEqual(speaker, "ベルベット")
        self.assertEqual(body, "治療してもらった恩があるから\n斬りたくないとでもいうの？")
        self.assertNotIn("M", body)

    def test_close_name_line_stays_out_of_the_sentence(self):
        text = assemble(
            [
                ("老人", (12, 0, 70, 24)),
                ("業魔病は、変わらず広がり続けている。実際に", (12, 28, 560, 52)),
                ("治安が保たれているのは、限られた大都市部だけだ", (12, 56, 540, 80)),
            ]
        )
        speaker, body = split_speaker(text)
        self.assertEqual(speaker, "老人")
        self.assertNotIn("老人", body)
        self.assertTrue(body.startswith("業魔病"))

    def test_wrapped_clause_stays_in_the_sentence(self):
        self.assertEqual(split_speaker("今日\nはいい天気ですね。散歩しましょう。")[0], "")
        self.assertEqual(split_speaker("変わらず\n広がり続けている。実際に問題だ。")[0], "")
        self.assertEqual(split_speaker("大都市\n部だけが治安を保っている。")[0], "")
        self.assertEqual(split_speaker("私\n行かないつもりで、ここで待っている。")[0], "")

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

    def test_english_and_noise_are_left_out(self):
        self.assertEqual(japanese_text("S"), "")
        self.assertEqual(japanese_text("S\nS"), "")
        self.assertEqual(japanese_text("INANTA"), "")
        self.assertEqual(japanese_text("INANTA\nINANTA"), "")
        self.assertEqual(japanese_text("Hello"), "")
        self.assertEqual(japanese_text("ＩＮＡＮＴＡ"), "")
        self.assertEqual(japanese_text("...\n123"), "")
        self.assertEqual(japanese_text("召窟前"), "召窟前")
        self.assertEqual(japanese_text("S\n召窟前\nINANTA"), "召窟前")
        self.assertEqual(japanese_text("OK\nここは洞窟の前"), "ここは洞窟の前")
        self.assertEqual(japanese_text("Levelが上がった"), "Levelが上がった")
        self.assertEqual(japanese_text("ﾃｽﾄ"), "ﾃｽﾄ")
        self.assertEqual(japanese_text("\x1e街人\nよう、外は寒かっただろ！"), "\x1e街人\nよう、外は寒かっただろ！")
        self.assertEqual(japanese_text("\x1eINANTA\nよう、外は寒かっただろ！"), "よう、外は寒かっただろ！")

    def test_vertical_columns_read_right_to_left(self):
        boxes = [(100, 0, 120, 200), (70, 0, 90, 200)]
        self.assertTrue(guess_vertical(boxes))
        text = assemble([("右", boxes[0]), ("左", boxes[1])])
        self.assertEqual(text, "右\n左")


if __name__ == "__main__":
    unittest.main()
