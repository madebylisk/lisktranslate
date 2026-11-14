import unittest

from lisktranslate.translate import Translator


class TranslateTests(unittest.TestCase):
    def test_cache_and_blank(self):
        calls = []

        def fake(text: str) -> str:
            calls.append(text)
            return "Hello"

        translator = Translator(translate=fake)
        self.assertEqual(translator.english("  "), "")
        self.assertEqual(translator.english("  こんにちは "), "Hello")
        self.assertEqual(translator.english("こんにちは"), "Hello")
        self.assertEqual(calls, ["こんにちは"])

    def test_long_text_is_split_on_lines(self):
        calls = []

        def fake(text: str) -> str:
            calls.append(text)
            return text

        translator = Translator(translate=fake)
        source = "あ" * 1000 + "\n" + "い" * 1000
        self.assertEqual(translator.english(source), source)
        self.assertEqual(calls, ["あ" * 1000, "い" * 1000])


if __name__ == "__main__":
    unittest.main()
