import json
import os
import tempfile
import unittest

from PySide6.QtWidgets import QApplication, QLabel

from lisktranslate.app import MainWindow
from lisktranslate.furigana import Token
from lisktranslate.panel import TEXT_STYLES, RubyWord, TextPanel, text_style


class TextStyleTests(unittest.TestCase):
    def test_unknown_values_stay_on_the_smallest_size(self):
        self.assertEqual(text_style(None).name, "Small")
        self.assertEqual(text_style(20).name, "Small")
        self.assertEqual(text_style("huge").name, "Small")
        self.assertEqual(text_style("Large").surface, 24)


class TextPanelSizeTests(unittest.TestCase):
    def setUp(self):
        self.app = QApplication.instance() or QApplication([])
        self.panel = TextPanel()

    def _label(self, text: str) -> QLabel:
        matches = [label for label in self.panel.findChildren(QLabel) if label.text() == text]
        self.assertEqual(len(matches), 1, text)
        return matches[0]

    def test_four_sizes_scale_japanese_and_english(self):
        sections = [("", "日本語", None, "Japanese", False)]
        ruby = [("", "あ", [Token("漢字", reading="かんじ", gap_before=8)], "", True)]
        for style in TEXT_STYLES:
            self.panel.set_style(style)
            self.panel.show_sections(sections)
            self.app.processEvents()
            self.assertEqual(self._label("日本語").font().pointSize(), style.japanese)
            self.assertEqual(self._label("Japanese").font().pointSize(), style.english)
            self.panel.show_sections(ruby)
            self.app.processEvents()
            word = self.panel.findChildren(RubyWord)[0]
            self.assertEqual(word.surface.font().pointSize(), style.surface)
            self.assertEqual(word.reading.font().pointSize(), style.reading)
        self.assertEqual(TEXT_STYLES[0].surface, 15)
        self.assertEqual(TEXT_STYLES[0].reading, 8)
        self.assertEqual(TEXT_STYLES[0].english, 13)


class TextSizeWindowTests(unittest.TestCase):
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
        self.window = MainWindow()
        for region in self.window.regions:
            region.hide()

    def tearDown(self):
        self.window.close()
        if self._old is None:
            os.environ.pop("LISKTRANSLATE_CONFIG", None)
        else:
            os.environ["LISKTRANSLATE_CONFIG"] = self._old

    def test_content_grows_and_the_buttons_stay_small(self):
        window = self.window
        self.assertEqual(
            [window.text_size_box.itemText(i) for i in range(window.text_size_box.count())],
            [style.name for style in TEXT_STYLES],
        )
        self.assertEqual(window.text_size_box.currentText(), "Small")
        window.show()
        self.app.processEvents()
        self.assertLessEqual(window.width(), 460)
        self.assertLessEqual(window.history_box.geometry().right(), window.width() - 8)
        button_size = window.add_button.font().pointSize()
        window.hide()

        region_id = window.regions[0].region_id
        window._on_batch(
            ([("ocr", region_id, "今日はいい天気ですね。", "The weather is nice today.", "")], "")
        )
        word = window.panel.findChildren(RubyWord)[0]
        self.assertEqual(word.surface.font().pointSize(), 15)
        self.assertEqual(word.reading.font().pointSize(), 8)
        english = [label for label in window.panel.findChildren(QLabel) if "weather" in label.text()]
        self.assertEqual(english[0].font().pointSize(), 13)

        width = window.width()
        window.text_size_box.setCurrentText("Extra large")
        self.app.processEvents()
        word = window.panel.findChildren(RubyWord)[0]
        self.assertEqual(word.surface.font().pointSize(), 30)
        self.assertEqual(word.reading.font().pointSize(), 16)
        english = [label for label in window.panel.findChildren(QLabel) if "weather" in label.text()]
        self.assertEqual(english[0].font().pointSize(), 26)
        self.assertEqual(window.add_button.font().pointSize(), button_size)
        self.assertEqual(window.furigana_box.font().pointSize(), button_size)
        self.assertEqual(window.width(), width)
        history_words = window.history.findChildren(RubyWord)
        self.assertGreaterEqual(len(history_words), 1)
        self.assertEqual(history_words[0].surface.font().pointSize(), 13)
        self.assertEqual(history_words[0].reading.font().pointSize(), 7)

        with open(self._path, encoding="utf-8") as handle:
            saved = json.load(handle)
        self.assertEqual(saved["text_size"], "Extra large")
        self.assertNotIn("menu_size", saved)

        again = MainWindow()
        try:
            self.assertEqual(again.text_size_box.currentText(), "Extra large")
            self.assertEqual(again.panel._style.surface, 30)
        finally:
            again.close()
            for region in again.regions:
                region.hide()
