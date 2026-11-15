import json
import os
import tempfile
import unittest

from PySide6.QtWidgets import QApplication

from lisktranslate.history_window import HistoryWindow
from lisktranslate.panel import RubyWord


class HistoryWindowTests(unittest.TestCase):
    def setUp(self):
        self.app = QApplication.instance() or QApplication([])
        self.window = HistoryWindow()

    def tearDown(self):
        self.window.force_close()

    def test_keeps_repeats_and_fills_the_latest_english(self):
        self.window.add_line("今日はいい天気", "", None)
        self.window.add_line("今日はいい天気", "The weather is nice", None)
        self.window.add_line("食べました", "", None)
        self.window.add_line("  ", "", None)
        self.assertEqual([row.japanese for row in self.window.entries], ["今日はいい天気", "食べました"])
        self.assertEqual(self.window.entries[0].english, "The weather is nice")
        self.window.set_english("食べました", "I ate")
        self.assertEqual(self.window.entries[1].english, "I ate")
        self.window.add_line("今日はいい天気", "", None)
        self.window.set_english("今日はいい天気", "Nice weather again")
        self.assertEqual(len(self.window.entries), 3)
        self.assertEqual(self.window.entries[0].english, "The weather is nice")
        self.assertEqual(self.window.entries[2].english, "Nice weather again")


class HistorySessionTests(unittest.TestCase):
    def setUp(self):
        self._old = os.environ.get("LISKTRANSLATE_CONFIG")
        self._dir = tempfile.mkdtemp()
        self._path = os.path.join(self._dir, "config.json")
        with open(self._path, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "paused": True,
                    "english": True,
                    "dictionary": False,
                    "history": False,
                    "hide_frames": True,
                    "regions": [{"x": 80, "y": 80, "w": 220, "h": 90, "rel": None}],
                },
                handle,
            )
        os.environ["LISKTRANSLATE_CONFIG"] = self._path
        self.app = QApplication.instance() or QApplication([])
        from lisktranslate.app import MainWindow

        self.window = MainWindow()

    def tearDown(self):
        self.window.close()
        if self._old is None:
            os.environ.pop("LISKTRANSLATE_CONFIG", None)
        else:
            os.environ["LISKTRANSLATE_CONFIG"] = self._old

    def test_session_lines_keep_compact_furigana(self):
        window = self.window
        window.show()
        self.app.processEvents()
        self.assertLessEqual(window.history_box.geometry().right(), window.width() - 8)
        self.assertLessEqual(window.width(), 460)
        window.hide()

        region_id = window.regions[0].region_id
        window._on_batch(
            ([("ocr", region_id, "今日はいい天気ですね。", "The weather is nice today.", "")], "")
        )
        window._on_batch(([("ocr", region_id, "食べました。", "", "")], ""))
        window._on_batch(([("translate", region_id, "食べました。", "I ate.", "")], ""))
        self.assertEqual(
            [row.japanese for row in window.history.entries],
            ["今日はいい天気ですね。", "食べました。"],
        )
        self.assertEqual(window.history.entries[0].english, "The weather is nice today.")
        self.assertEqual(window.history.entries[1].english, "I ate.")

        words = window.history.findChildren(RubyWord)
        self.assertGreaterEqual(len(words), 4)
        for word in words:
            self.assertLessEqual(word.layout().contentsMargins().left(), 1)
            self.assertEqual(word.surface.font().pointSize(), 13)
            self.assertEqual(word.reading.font().pointSize(), 7)
        readings = [word.reading.text() for word in words]
        self.assertIn("きょう", readings)
        self.assertIn("てんき", readings)

        window.history.show()
        self.app.processEvents()
        japanese = window.history.entries[0].flow
        english = window.history.entries[0].english_label
        self.assertIsNotNone(japanese)
        self.assertGreater(english.mapTo(window.history, english.rect().topLeft()).y(), japanese.y())
        window.history.hide()

        with open(self._path, encoding="utf-8") as handle:
            saved = json.load(handle)
        self.assertNotIn("lines", saved)
        self.assertNotIn("history_lines", saved)
