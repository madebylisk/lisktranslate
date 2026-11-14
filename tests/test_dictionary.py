import unittest

from lisktranslate.dictionary import Dictionary, dictionary_ready, format_kanji, headword, pick_word
from lisktranslate.furigana import Token


class _Form:
    def __init__(self, text, pri=None):
        self.text = text
        self.pri = pri or []


class _Gloss:
    def __init__(self, text, lang="eng"):
        self.text = text
        self.lang = lang


class _Sense:
    def __init__(self, glosses, name_type=None, stagr=None, stagk=None):
        self.gloss = glosses
        self.name_type = name_type or []
        self.stagr = stagr or []
        self.stagk = stagk or []


class _Entry:
    def __init__(self, kanji, kana, senses, common=False):
        self.kanji_forms = [_Form(text, ["news1"] if common else []) for text in kanji]
        self.kana_forms = [_Form(text) for text in kana]
        self.senses = senses


class _Reading:
    def __init__(self, r_type, value):
        self.r_type = r_type
        self.value = value


class _Group:
    def __init__(self, readings):
        self.readings = readings
        self.meanings = []


class _Char:
    def __init__(self):
        self.literal = "日"
        self.rm_groups = [_Group([_Reading("ja_kun", "ひ"), _Reading("ja_on", "ニチ"), _Reading("pinyin", "ri4")])]

    def meanings(self, english_only=False):
        return ["day", "sun"]


class _Result:
    def __init__(self, entries=None, names=None):
        self.entries = entries or []
        self.names = names or []


class _Jam:
    def __init__(self):
        self.queries = []

    def lookup(self, query, lookup_chars=False, lookup_ne=False):
        self.queries.append((query, lookup_ne))
        today = _Entry(["今日"], ["きょう", "こんにち"], [_Sense([_Gloss("today")]), _Sense([_Gloss("nowadays")])])
        if query == "今日":
            return _Result([today])
        if query == "田中":
            return _Result(names=[_Entry(["田中"], ["たなか"], [_Sense([], ["surname"])])])
        return _Result()

    def get_char(self, character):
        char = _Char()
        char.literal = character
        return char


class DictionaryTests(unittest.TestCase):
    def test_headword_keeps_kanji_words_and_skips_particles(self):
        self.assertEqual(headword(Token("は", pos="助詞", lemma="は", kana="は")), "")
        self.assertEqual(headword(Token("食べ", pos="動詞", lemma="食べる", kana="たべ")), "食べる")
        self.assertEqual(headword(Token("いい", pos="形容詞", lemma="良い", kana="いい")), "良い")

    def test_pick_word_matches_the_reading(self):
        entry = _Entry(
            ["今日"],
            ["きょう", "こんにち"],
            [
                _Sense([_Gloss("today")]),
                _Sense([_Gloss("nowadays")], stagr=["こんにち"]),
            ],
            common=True,
        )
        other = _Entry(["今日"], ["こんにち"], [_Sense([_Gloss("these days")])])
        gloss = pick_word([other, entry], "今日", "きょう")
        self.assertEqual(gloss.written, "今日")
        self.assertEqual(gloss.reading, "きょう")
        self.assertIn("today", gloss.meanings)
        self.assertNotIn("nowadays", gloss.meanings)

    def test_kanji_readings_skip_other_languages(self):
        gloss = format_kanji(_Char())
        self.assertEqual(gloss.character, "日")
        self.assertIn("ひ", gloss.readings)
        self.assertIn("ニチ", gloss.readings)
        self.assertNotIn("ri4", gloss.readings)
        self.assertEqual(gloss.meanings, "day, sun")

    def test_explain_uses_lemmas_and_lists_each_kanji(self):
        jam = _Jam()
        page = Dictionary(jam=jam).explain(
            [
                Token("今日", lemma="今日", pos="名詞", kana="きょう"),
                Token("は", lemma="は", pos="助詞", kana="は"),
                Token("田中", lemma="田中", pos="名詞", kana="たなか"),
            ]
        )
        self.assertEqual(page.words[0].reading, "きょう")
        self.assertEqual(page.words[1].meanings, "surname")
        self.assertEqual([item.character for item in page.kanji], ["今", "日", "田", "中"])

    @unittest.skipUnless(dictionary_ready(), "offline dictionary is not installed")
    def test_live_lookup_keeps_the_reading_that_matches(self):
        page = Dictionary().explain([Token("今日", lemma="今日", pos="名詞", kana="きょう")])
        self.assertEqual(page.words[0].written, "今日")
        self.assertEqual(page.words[0].reading, "きょう")
        self.assertIn("today", page.words[0].meanings)
        self.assertNotIn("nowadays", page.words[0].meanings)
        self.assertEqual(page.kanji[0].character, "今")
        self.assertIn("now", page.kanji[0].meanings)


if __name__ == "__main__":
    unittest.main()
