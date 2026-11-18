import json
import os
import tempfile
import unittest
from pathlib import Path

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
        self.window.add_line("Region 1", "今日はいい天気", "", None)
        self.window.add_line("Region 1", "今日はいい天気", "The weather is nice", None)
        self.window.add_line("Region 1", "食べました", "", None)
        self.window.add_line("Region 1", "  ", "", None)
        page = self.window.page("Region 1")
        self.assertEqual([row.japanese for row in page.entries], ["今日はいい天気", "食べました"])
        self.assertEqual(page.entries[0].english, "The weather is nice")
        self.window.set_english("Region 1", "食べました", "I ate")
        self.assertEqual(page.entries[1].english, "I ate")
        self.window.add_line("Region 1", "今日はいい天気", "", None)
        self.window.set_english("Region 1", "今日はいい天気", "Nice weather again")
        self.assertEqual(len(page.entries), 3)
        self.assertEqual(page.entries[0].english, "The weather is nice")
        self.assertEqual(page.entries[2].english, "Nice weather again")

    def test_each_region_has_its_own_tab(self):
        self.window.add_line("Region 1", "今日", "today", None)
        self.window.add_line("Region 2", "明日", "tomorrow", None)
        self.assertEqual(self.window.tabs.count(), 2)
        self.assertEqual(self.window.tabs.tabText(0), "Region 1")
        self.assertEqual(self.window.tabs.tabText(1), "Region 2")
        self.window.set_english("Region 2", "明日", "Tomorrow")
        self.assertEqual(self.window.page("Region 1").entries[0].english, "today")
        self.assertEqual(self.window.page("Region 2").entries[0].english, "Tomorrow")


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
        page = window.history.page("Region 1")
        self.assertEqual(
            [row.japanese for row in page.entries],
            ["今日はいい天気ですね。", "食べました。"],
        )
        self.assertEqual(page.entries[0].english, "The weather is nice today.")
        self.assertEqual(page.entries[1].english, "I ate.")

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
        japanese = page.entries[0].flow
        english = page.entries[0].english_label
        self.assertIsNotNone(japanese)
        self.assertGreater(english.mapTo(window.history, english.rect().topLeft()).y(), japanese.y())
        window.history.hide()

        with open(self._path, encoding="utf-8") as handle:
            saved = json.load(handle)
        self.assertNotIn("lines", saved)
        self.assertNotIn("history_lines", saved)

        folder = os.path.join(self._dir, "history")
        window._on_history_folder(folder)
        files = list(Path(folder).rglob("*.txt"))
        self.assertEqual(len(files), 1)
        stored = files[0].read_text(encoding="utf-8")
        self.assertIn("今日（きょう）", stored)
        self.assertIn("天気（てんき）", stored)
        self.assertIn("The weather is nice today.", stored)
        self.assertIn("I ate.", stored)
