import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from lisktranslate.history_log import HistoryLog, history_path, safe_name


class HistoryLogTests(unittest.TestCase):
    def test_names_and_paths_stay_sortable(self):
        self.assertEqual(safe_name("A/B: C", "General"), "A B C")
        when = datetime(2026, 11, 15, 7, 55, 12)
        path = history_path(Path("Dropbox"), "Berseria", "Region 1", when)
        self.assertEqual(
            path.as_posix(),
            "Dropbox/Berseria/2026-11/2026-11-15/Region 1.txt",
        )

    def test_regions_are_separate_files_and_english_fills_in(self):
        root = Path(tempfile.mkdtemp())
        when = datetime(2026, 11, 15, 7, 55, 12)
        log = HistoryLog(root, now=lambda: when)
        log.add("Berseria", "Region 1", "今日はいい天気ですね。", "The weather is nice today.")
        log.add("Berseria", "Region 2", "食べました。", "")
        log.set_english("Berseria", "Region 2", "食べました。", "I ate.")
        first = (root / "Berseria" / "2026-11" / "2026-11-15" / "Region 1.txt").read_text(encoding="utf-8")
        second = (root / "Berseria" / "2026-11" / "2026-11-15" / "Region 2.txt").read_text(encoding="utf-8")
        self.assertIn("07:55:12", first)
        self.assertIn("今日はいい天気ですね。", first)
        self.assertIn("The weather is nice today.", first)
        self.assertNotIn("食べました。", first)
        self.assertEqual(second.count("食べました。"), 1)
        self.assertIn("I ate.", second)
        self.assertNotIn("---", second)

    def test_a_later_line_keeps_what_was_already_in_the_file(self):
        root = Path(tempfile.mkdtemp())
        path = root / "General" / "2026-11" / "2026-11-15" / "Region 1.txt"
        path.parent.mkdir(parents=True)
        path.write_text("yesterday\n", encoding="utf-8")
        when = datetime(2026, 11, 15, 8, 0, 0)
        log = HistoryLog(root, now=lambda: when)
        log.add("General", "Region 1", "今日", "Today")
        log.add("General", "Region 1", "明日", "Tomorrow")
        text = path.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("yesterday\n"))
        self.assertEqual(text.count("---"), 2)
        self.assertLess(text.index("今日"), text.index("明日"))

    def test_furigana_is_what_gets_written_and_english_still_fills_in(self):
        root = Path(tempfile.mkdtemp())
        when = datetime(2026, 11, 15, 7, 55, 12)
        log = HistoryLog(root, now=lambda: when)
        line = "今日（きょう）はいい天気（てんき）ですね。"
        log.add("Berseria", "Region 1", "今日はいい天気ですね。", "", line)
        log.add("Berseria", "Region 1", "今日はいい天気ですね。", "The weather is nice today.", line)
        log.add("Berseria", "Region 1", "食べました。", "")
        text = (root / "Berseria" / "2026-11" / "2026-11-15" / "Region 1.txt").read_text(encoding="utf-8")
        self.assertIn(line, text)
        self.assertEqual(text.count(line), 1)
        self.assertIn("The weather is nice today.", text)
        self.assertIn("食べました。", text)
        self.assertLess(text.index(line), text.index("The weather is nice today."))
        self.assertLess(text.index("The weather is nice today."), text.index("食べました。"))
