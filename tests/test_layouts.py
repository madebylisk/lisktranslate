import json
import os
import tempfile
import unittest

from PySide6.QtWidgets import QApplication, QInputDialog, QMessageBox

from lisktranslate.app import MainWindow, normalize_layouts


class NormalizeLayoutTests(unittest.TestCase):
    def test_keeps_named_regions_and_drops_broken_ones(self):
        layouts = normalize_layouts(
            {
                " Berseria ": {
                    "bound_title": "Tales",
                    "regions": [{"x": 1, "y": 2, "w": 3, "h": 4, "rel": [5, 6, 7, 8]}],
                },
                "": {"regions": []},
                "bad": "nope",
                "skip": {"regions": [{"x": 1}]},
            }
        )
        self.assertEqual(list(layouts), ["Berseria", "skip"])
        self.assertEqual(layouts["skip"]["regions"], [])
        self.assertEqual(layouts["Berseria"]["bound_title"], "Tales")
        self.assertEqual(layouts["Berseria"]["regions"][0]["rel"], [5, 6, 7, 8])


class LayoutWindowTests(unittest.TestCase):
    def setUp(self):
        self._old = os.environ.get("LISKTRANSLATE_CONFIG")
        self._dir = tempfile.mkdtemp()
        self._path = os.path.join(self._dir, "config.json")
        with open(self._path, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "paused": True,
                    "english": False,
                    "dictionary": False,
                    "hide_frames": True,
                    "regions": [{"x": 80, "y": 80, "w": 220, "h": 90, "rel": None}],
                },
                handle,
            )
        os.environ["LISKTRANSLATE_CONFIG"] = self._path
        self.app = QApplication.instance() or QApplication([])
        self.window = MainWindow()

    def tearDown(self):
        self.window.close()
        if self._old is None:
            os.environ.pop("LISKTRANSLATE_CONFIG", None)
        else:
            os.environ["LISKTRANSLATE_CONFIG"] = self._old

    def _pick(self, name: str) -> None:
        box = self.window.layout_box
        index = box.findText(name)
        box.setCurrentIndex(index)
        box.activated.emit(index)

    def _box(self):
        region = self.window.regions[0]
        return (region.x(), region.y(), region.width(), region.height())

    def test_save_switch_reload_and_delete(self):
        window = self.window
        window.show()
        self.app.processEvents()
        row_right = window.delete_layout_button.mapTo(
            window, window.delete_layout_button.rect().bottomRight()
        ).x()
        self.assertGreater(window.layout_box.width(), 40)
        self.assertLess(row_right, window.width() - 8)
        self.assertEqual(window.layout_box.placeholderText(), "Layout")
        window.hide()

        region = window.regions[0]
        region.setGeometry(120, 140, 240, 100)
        answers = iter([("Berseria", True)])

        def fake_text(*_args, **_kwargs):
            return next(answers)

        original_text = QInputDialog.getText
        QInputDialog.getText = staticmethod(fake_text)
        try:
            window._save_layout_as()
        finally:
            QInputDialog.getText = original_text
        self.assertEqual(window.layout_box.currentText(), "Berseria")
        self.assertEqual(self._box(), (120, 140, 240, 100))

        region = window.regions[0]
        region.setGeometry(400, 260, 180, 70)
        window._store_layout("Arise")
        window._fill_layouts()
        self.assertEqual(window.layout_box.currentText(), "Arise")

        self._pick("Berseria")
        self.assertEqual(self._box(), (120, 140, 240, 100))
        self.assertEqual(window.layout_box.currentText(), "Berseria")
        self._pick("Arise")
        self.assertEqual(self._box(), (400, 260, 180, 70))

        window.regions[0].setGeometry(30, 40, 200, 80)
        choices = iter(
            [
                QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.No,
            ]
        )
        original_question = QMessageBox.question
        QMessageBox.question = staticmethod(lambda *_args, **_kwargs: next(choices))
        try:
            self._pick("Berseria")
            self.assertEqual(window.layout_box.currentText(), "Arise")
            self.assertEqual(self._box()[:2], (30, 40))
            self._pick("Berseria")
        finally:
            QMessageBox.question = original_question
        self.assertEqual(window._layouts["Arise"]["regions"][0]["x"], 400)
        self.assertEqual(self._box(), (120, 140, 240, 100))

        self._pick("Arise")
        window.regions[0].setGeometry(30, 40, 200, 80)
        QMessageBox.question = staticmethod(
            lambda *_args, **_kwargs: QMessageBox.StandardButton.Yes
        )
        try:
            self._pick("Arise")
            self.assertEqual(window._layouts["Arise"]["regions"][0]["x"], 30)
            self.assertEqual(self._box()[:2], (30, 40))
            kept = self._box()
            window._delete_layout()
        finally:
            QMessageBox.question = original_question

        self.assertNotIn("Arise", window._layouts)
        self.assertIn("Berseria", window._layouts)
        self.assertEqual(window.layout_box.currentIndex(), -1)
        self.assertFalse(window.delete_layout_button.isEnabled())
        self.assertEqual(self._box(), kept)
        with open(self._path, encoding="utf-8") as handle:
            saved = json.load(handle)
        self.assertEqual(saved["layout"], "")
        self.assertIn("Berseria", saved["layouts"])
        self.assertNotIn("Arise", saved["layouts"])
        self.assertEqual(saved["regions"][0]["x"], 30)
