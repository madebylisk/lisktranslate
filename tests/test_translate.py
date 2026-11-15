import unittest

from lisktranslate.translate import Translator, _with_retry


class TranslateTests(unittest.TestCase):
    def test_cache_and_blank(self):
        calls = []

        def fake(texts):
            calls.append(list(texts))
            return ["Hello" for _ in texts]

        translator = Translator(translate=fake)
        self.assertEqual(translator.english("  "), "")
        self.assertEqual(translator.english("  こんにちは "), "Hello")
        self.assertEqual(translator.english("こんにちは"), "Hello")
        self.assertEqual(calls, [["こんにちは"]])

    def test_many_lines_share_one_request(self):
        calls = []

        def fake(texts):
            calls.append(list(texts))
            return [f"en:{text}" for text in texts]

        translator = Translator(translate=fake)
        self.assertEqual(
            translator.english_many(["今日", "天気", "今日"]),
            ["en:今日", "en:天気", "en:今日"],
        )
        self.assertEqual(calls, [["今日", "天気"]])

    def test_long_text_is_split_on_lines(self):
        calls = []

        def fake(texts):
            calls.append(list(texts))
            return list(texts)

        translator = Translator(translate=fake)
        source = "あ" * 1000 + "\n" + "い" * 1000
        self.assertEqual(translator.english(source), source)
        self.assertEqual(calls, [["あ" * 1000, "い" * 1000]])

    def test_busy_response_is_retried(self):
        tries = {"n": 0}
        slept = []

        def post(texts):
            tries["n"] += 1
            if tries["n"] == 1:
                raise RuntimeError("HTTP 429")
            return ["Hi" for _ in texts]

        self.assertEqual(_with_retry(post, ["こんにちは"], sleep=slept.append), ["Hi"])
        self.assertEqual(slept, [0.8])
        self.assertEqual(tries["n"], 2)


if __name__ == "__main__":
    unittest.main()
