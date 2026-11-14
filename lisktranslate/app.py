"""LiskTranslate window: regions, capture loop, and the text panel."""

from __future__ import annotations

import queue

from PySide6.QtCore import QPoint, QRect, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from lisktranslate import config, win32
from lisktranslate.capture import (
    dip_rect_to_physical,
    grab_screen,
    grab_window,
    physical_rect_to_dip,
)
from lisktranslate.detect import FrameTracker
from lisktranslate.dictionary import Dictionary, dictionary_ready
from lisktranslate.dictionary_window import DictionaryWindow
from lisktranslate.furigana import Furigana
from lisktranslate.ocr_engine import OcrService
from lisktranslate.panel import TextPanel
from lisktranslate.region import RegionFrame
from lisktranslate.translate import Translator


class _Worker(QThread):
    status = Signal(str)
    batch_done = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self._queue: queue.Queue = queue.Queue()
        self.service: OcrService | None = None
        self.want_english = True
        self._translator: Translator | None = None

    def submit(self, batch: list[tuple[int, object]]) -> None:
        self._queue.put(("ocr", batch))

    def submit_translations(self, batch: list[tuple[int, str]]) -> None:
        self._queue.put(("translate", batch))

    def stop(self) -> None:
        self._queue.put(None)

    def _english(self, text: str) -> tuple[str, str]:
        if not self.want_english or not text.strip():
            return "", ""
        try:
            if self._translator is None:
                self._translator = Translator()
            return self._translator.english(text), ""
        except Exception as exc:
            return "", str(exc)

    def run(self) -> None:
        try:
            self.service = OcrService()
            self.status.emit(self.service.status_line)
        except Exception as exc:
            self.status.emit(str(exc))
            self.service = None
        while True:
            job = self._queue.get()
            if job is None:
                return
            kind, batch = job
            results = []
            if kind == "translate":
                for region_id, text in batch:
                    english, err = self._english(text)
                    results.append(("translate", region_id, text, english, err))
            else:
                for region_id, image in batch:
                    if self.service is None or not self.service.available:
                        message = self.service.status_line if self.service else "OCR is unavailable."
                        results.append(("ocr", region_id, "", "", message))
                        continue
                    try:
                        text = self.service.recognize(image)
                    except Exception as exc:
                        results.append(("ocr", region_id, "", "", str(exc)))
                        continue
                    english, err = self._english(text)
                    results.append(("ocr", region_id, text, english, err))
            engine = self.service.engine_name if self.service else "unavailable"
            self.batch_done.emit((results, engine))


class _DictWorker(QThread):
    status = Signal(str)
    page_ready = Signal(int, object)

    def __init__(self) -> None:
        super().__init__()
        self._queue: queue.Queue = queue.Queue()
        self._dictionary: Dictionary | None = None

    def submit(self, generation: int, tokens) -> None:
        self._queue.put((generation, tokens))

    def stop(self) -> None:
        self._queue.put(None)

    def _shutdown(self) -> None:
        dictionary = self._dictionary
        self._dictionary = None
        if dictionary is None:
            return
        jam = dictionary._jam
        dictionary._jam = None
        context = getattr(jam, "_Jamdict__jm_ctx", None)
        if context is not None:
            try:
                context.close()
            except Exception:
                pass
            setattr(jam, "_Jamdict__jm_ctx", None)

    def run(self) -> None:
        try:
            while True:
                job = self._queue.get()
                if job is None:
                    return
                while True:
                    try:
                        newer = self._queue.get_nowait()
                    except queue.Empty:
                        break
                    if newer is None:
                        return
                    job = newer
                generation, tokens = job
                if self._dictionary is None:
                    try:
                        if not dictionary_ready():
                            self.status.emit("Downloading the offline dictionary…")
                        self._dictionary = Dictionary()
                        self.status.emit("")
                    except Exception as exc:
                        self.status.emit(f"Dictionary unavailable. {exc}")
                        continue
                try:
                    self.page_ready.emit(generation, self._dictionary.explain(tokens))
                except Exception as exc:
                    self.status.emit(f"Dictionary unavailable. {exc}")
        finally:
            self._shutdown()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("LiskTranslate")
        self.regions: list[RegionFrame] = []
        self.trackers: dict[int, FrameTracker] = {}
        self.bound_hwnd = 0
        self.bound_title = ""
        self._next_id = 1
        self._inflight = False
        self._translate_after = False
        self._picking = False
        self._saw_click = False
        self._closing = False
        self._ticks = 0
        self._dict_worker: _DictWorker | None = None
        self._dict_generation = 0
        self._dict_signature: tuple | None = None
        self._dictionary_placed = False
        self._saved = config.load()
        self.furigana = self._load_furigana()
        self._build()
        self._restore()
        self.worker = _Worker()
        self.worker.want_english = self.english_box.isChecked()
        self.worker.status.connect(self._set_engine)
        self.worker.batch_done.connect(self._on_batch)
        self.worker.start()
        if self.dictionary_box.isChecked():
            self._on_dictionary(True)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(100)
        self._pick_timer = QTimer(self)
        self._pick_timer.timeout.connect(self._poll_pick)

    def _load_furigana(self) -> Furigana | None:
        try:
            return Furigana()
        except Exception:
            return None

    def _build(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        self.status = QLabel("Starting OCR…")
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color: #a1a1aa;")
        layout.addWidget(self.status)

        buttons = QHBoxLayout()
        self.add_button = QPushButton("Add region")
        self.remove_button = QPushButton("Remove")
        self.bind_button = QPushButton("Bind window")
        self.pause_button = QPushButton("Pause")
        self.pause_button.setCheckable(True)
        self.add_button.clicked.connect(self._add_default_region)
        self.remove_button.clicked.connect(self._remove_menu)
        self.bind_button.clicked.connect(self._toggle_bind)
        self.pause_button.toggled.connect(self._on_pause)
        buttons.addWidget(self.add_button)
        buttons.addWidget(self.remove_button)
        buttons.addWidget(self.bind_button)
        buttons.addWidget(self.pause_button)
        layout.addLayout(buttons)

        self.furigana_box = QCheckBox("Furigana")
        self.furigana_box.setChecked(bool(self._saved.get("furigana", True)))
        if self.furigana is None:
            self.furigana_box.setChecked(False)
            self.furigana_box.setEnabled(False)
        self.english_box = QCheckBox("English")
        self.english_box.setChecked(bool(self._saved.get("english", True)))
        self.spacing_box = QCheckBox("Spacing")
        self.spacing_box.setToolTip("Separate words and particles")
        self.spacing_box.setChecked(bool(self._saved.get("spacing", True)))
        if self.furigana is None:
            self.spacing_box.setChecked(False)
            self.spacing_box.setEnabled(False)
        self.click_box = QCheckBox("Click through")
        self.click_box.setChecked(bool(self._saved.get("click_through", False)))
        self.hide_box = QCheckBox("Hide frames")
        self.hide_box.setChecked(bool(self._saved.get("hide_frames", False)))
        self.dictionary_box = QCheckBox("Dictionary")
        self.dictionary_box.setToolTip("Look up kanji offline")
        self.dictionary_box.setChecked(bool(self._saved.get("dictionary", False)))
        self.furigana_box.toggled.connect(self._on_options)
        self.spacing_box.toggled.connect(self._on_options)
        self.english_box.toggled.connect(self._on_english)
        self.click_box.toggled.connect(self._on_options)
        self.hide_box.toggled.connect(self._on_options)
        self.dictionary_box.toggled.connect(self._on_dictionary)
        reading = QHBoxLayout()
        reading.addWidget(self.furigana_box)
        reading.addWidget(self.spacing_box)
        reading.addWidget(self.english_box)
        reading.addStretch(1)
        layout.addLayout(reading)
        chrome = QHBoxLayout()
        chrome.addWidget(self.click_box)
        chrome.addWidget(self.hide_box)
        chrome.addWidget(self.dictionary_box)
        chrome.addStretch(1)
        layout.addLayout(chrome)

        self.panel = TextPanel()
        layout.addWidget(self.panel, 1)
        self.dictionary = DictionaryWindow()
        self.dictionary.closed.connect(self._on_dictionary_closed)

        copy = QPushButton("Copy text")
        copy.clicked.connect(self._copy)
        layout.addWidget(copy)

        self._engine = "Starting OCR…"
        self.resize(440, 580)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        win32.exclude_from_capture(int(self.winId()))

    def _on_pause(self, _checked: bool) -> None:
        self._set_status()
        self._save()

    def _remove_menu(self) -> None:
        if not self.regions:
            return
        menu = QMenu(self)
        actions = {}
        for region in self.regions:
            actions[menu.addAction(f"Region {region.index}")] = region
        chosen = menu.exec(self.remove_button.mapToGlobal(QPoint(0, self.remove_button.height())))
        region = actions.get(chosen)
        if region is not None:
            self._remove_region(region)

    def _restore(self) -> None:
        window = self._saved.get("window")
        if isinstance(window, dict) and {"x", "y", "w", "h"} <= window.keys():
            self.setGeometry(int(window["x"]), int(window["y"]), int(window["w"]), int(window["h"]))
        else:
            screen = QGuiApplication.primaryScreen().availableGeometry()
            self.move(screen.right() - 480, screen.top() + 48)
        self.pause_button.blockSignals(True)
        self.pause_button.setChecked(bool(self._saved.get("paused", False)))
        self.pause_button.blockSignals(False)
        items = self._saved.get("regions") or []
        if items:
            for item in items:
                rel = tuple(item["rel"]) if item.get("rel") else None
                self._add_region(
                    QRect(int(item["x"]), int(item["y"]), int(item["w"]), int(item["h"])),
                    rel,
                )
        else:
            self._add_default_region()
        title = self._saved.get("bound_title") or ""
        if title:
            hwnd = win32.find_window_by_title(title)
            if hwnd and hwnd not in self._our_hwnds():
                self._bind(hwnd, keep_existing_rel=True)
        self._apply_chrome()
        self._refresh_panel()

    def _add_default_region(self) -> None:
        screen = QGuiApplication.primaryScreen().availableGeometry()
        width, height = 520, 150
        offset = 28 * len(self.regions)
        x = screen.x() + max(20, (screen.width() - width) // 2) + offset
        y = screen.y() + screen.height() - height - 180 - offset
        self._add_region(QRect(x, y, width, height), None)
        if self.bound_hwnd:
            self._write_rel(self.regions[-1])
        self._save()

    def _add_region(self, rect: QRect, rel) -> RegionFrame:
        region = RegionFrame(self._next_id, len(self.regions) + 1)
        self._next_id += 1
        region.setGeometry(rect)
        region.rel = tuple(rel) if rel else None
        region.remove_requested.connect(self._remove_region)
        region.drag_finished.connect(self._on_drag_finished)
        region.show()
        self.regions.append(region)
        self.trackers[region.region_id] = FrameTracker()
        self._renumber()
        self._apply_chrome()
        return region

    def _remove_region(self, region: RegionFrame) -> None:
        if region not in self.regions:
            return
        self.regions.remove(region)
        self.trackers.pop(region.region_id, None)
        region.close()
        region.deleteLater()
        self._renumber()
        self._refresh_panel()
        self._save()

    def _renumber(self) -> None:
        for index, region in enumerate(self.regions, 1):
            region.set_index(index)

    def _on_drag_finished(self, region: RegionFrame) -> None:
        if self.bound_hwnd:
            self._write_rel(region)
        tracker = self.trackers.get(region.region_id)
        if tracker is not None:
            tracker.reset_image()
        self._save()

    def _on_options(self) -> None:
        self._apply_chrome()
        self._refresh_panel()
        self._save()

    def _on_english(self, checked: bool) -> None:
        self.worker.want_english = checked
        self._save()
        if not checked:
            self._refresh_panel()
            return
        if self._inflight:
            self._translate_after = True
            return
        self._request_translations()

    def _on_dictionary(self, checked: bool) -> None:
        if checked:
            self._place_dictionary()
            self.dictionary.show()
            self.dictionary.raise_()
            self.dictionary.activateWindow()
            self._ensure_dict_worker()
            self._dict_signature = None
            self._refresh_panel()
        else:
            self.dictionary.hide()
        self._save()

    def _on_dictionary_closed(self) -> None:
        self.dictionary_box.blockSignals(True)
        self.dictionary_box.setChecked(False)
        self.dictionary_box.blockSignals(False)
        self._save()

    def _place_dictionary(self) -> None:
        if self._dictionary_placed:
            return
        self._dictionary_placed = True
        saved = self._saved.get("dictionary_window")
        if isinstance(saved, dict) and {"x", "y", "w", "h"} <= saved.keys():
            self.dictionary.setGeometry(int(saved["x"]), int(saved["y"]), int(saved["w"]), int(saved["h"]))
            return
        self.dictionary.resize(400, 580)
        self.dictionary.move(max(0, self.x() - 416), self.y())

    def _ensure_dict_worker(self) -> None:
        if self._dict_worker is not None:
            return
        self._dict_worker = _DictWorker()
        self._dict_worker.status.connect(self._on_dict_status)
        self._dict_worker.page_ready.connect(self._on_dict_page)
        self._dict_worker.start()

    def _on_dict_status(self, text: str) -> None:
        if text:
            self.dictionary.show_message(text)

    def _on_dict_page(self, generation: int, page) -> None:
        if generation != self._dict_generation or page is None:
            return
        self.dictionary.show_page(page)

    def _refresh_dictionary(self, tokens) -> None:
        if not self.dictionary_box.isChecked() or not self.dictionary.isVisible():
            return
        if self.furigana is None:
            self.dictionary.show_message("The tokenizer is unavailable.")
            return
        signature = tuple(
            (token.surface, token.lemma, token.kana, token.pos)
            for token in tokens
            if token.surface and not token.break_line
        )
        if signature == self._dict_signature:
            return
        self._dict_signature = signature
        if not signature:
            self.dictionary.show_message("Kanji from the recognized text show up here.")
            return
        self._ensure_dict_worker()
        self._dict_generation += 1
        if not self.dictionary.has_page:
            self.dictionary.show_message("Loading dictionary…")
        worker = self._dict_worker
        if worker is not None:
            worker.submit(self._dict_generation, list(tokens))

    def _request_translations(self) -> None:
        batch = [
            (region.region_id, self.trackers[region.region_id].text)
            for region in self.regions
            if self.trackers[region.region_id].text.strip()
            and not self.trackers[region.region_id].english.strip()
        ]
        if not batch:
            self._refresh_panel()
            return
        self._inflight = True
        self.worker.submit_translations(batch)

    def _apply_chrome(self) -> None:
        hidden = self.hide_box.isChecked()
        click = self.click_box.isChecked() or hidden
        for region in self.regions:
            region.set_frame_hidden(hidden)
            region.set_click_through(click)

    def _toggle_bind(self) -> None:
        if self._picking:
            self._stop_pick()
            return
        if self.bound_hwnd:
            self._unbind()
            return
        self._picking = True
        self._saw_click = False
        self.bind_button.setText("Click the game window…")
        self._set_status()
        self._pick_timer.start(30)

    def _stop_pick(self) -> None:
        self._picking = False
        self._saw_click = False
        self._pick_timer.stop()
        self.bind_button.setText("Unbind" if self.bound_hwnd else "Bind window")
        self._set_status()

    def _poll_pick(self) -> None:
        if win32.key_down(0x1B):
            self._stop_pick()
            return
        if win32.key_down(0x01):
            self._saw_click = True
            return
        if not self._saw_click:
            return
        self._saw_click = False
        hwnd = win32.root_at_cursor()
        if not hwnd or hwnd in self._our_hwnds():
            return
        self._stop_pick()
        self._bind(hwnd, keep_existing_rel=False)

    def _bind(self, hwnd: int, keep_existing_rel: bool) -> None:
        self.bound_hwnd = hwnd
        self.bound_title = win32.window_title(hwnd)
        for region in self.regions:
            if not (keep_existing_rel and region.rel):
                self._write_rel(region)
        self._follow()
        self.bind_button.setText("Unbind")
        self._set_status()
        self._save()

    def _unbind(self, note: str = "") -> None:
        self.bound_hwnd = 0
        self.bound_title = ""
        for region in self.regions:
            region.rel = None
        self.bind_button.setText("Bind window")
        if note:
            self.status.setText(note)
        else:
            self._set_status()
        self._save()

    def _our_hwnds(self) -> set[int]:
        hwnds = {int(self.winId())}
        for region in self.regions:
            hwnds.add(int(region.winId()))
        return hwnds

    def _write_rel(self, region: RegionFrame) -> None:
        if not self.bound_hwnd:
            region.rel = None
            return
        try:
            left, top, _right, _bottom = win32.window_rect(self.bound_hwnd)
        except OSError:
            return
        x, y, width, height = dip_rect_to_physical(region.geometry())
        region.rel = (x - left, y - top, width, height)

    def _follow(self) -> None:
        if not self.bound_hwnd:
            return
        if not win32.is_window(self.bound_hwnd):
            self._unbind("The bound window closed.")
            return
        try:
            left, top, _right, _bottom = win32.window_rect(self.bound_hwnd)
        except OSError:
            return
        for region in self.regions:
            if region.dragging or not region.rel:
                continue
            rx, ry, rw, rh = region.rel
            rect = physical_rect_to_dip(left + rx, top + ry, rw, rh)
            if region.geometry() != rect:
                region.setGeometry(rect)
                region.ensure_input_mode()

    def _tick(self) -> None:
        self._follow()
        self._ticks += 1
        if self.pause_button.isChecked() or self._inflight or self._ticks % 3:
            return
        batch = []
        for region in self.regions:
            if region.dragging:
                continue
            tracker = self.trackers[region.region_id]
            image = self._capture(region)
            if image is None:
                continue
            if tracker.wants_ocr(image):
                batch.append((region.region_id, image))
        if not batch:
            return
        self._inflight = True
        self.worker.submit(batch)

    def _capture(self, region: RegionFrame):
        if self.bound_hwnd and region.rel and not win32.is_minimized(self.bound_hwnd):
            image = grab_window(self.bound_hwnd, region.rel)
            if image is not None:
                return image
        try:
            return grab_screen(region.geometry())
        except (OSError, ValueError):
            return None

    def _on_batch(self, payload) -> None:
        if self._closing:
            self._inflight = False
            return
        results, engine = payload
        self._inflight = False
        if engine:
            self._engine = engine
        error = ""
        changed = False
        for kind, region_id, text, english, err in results:
            tracker = self.trackers.get(region_id)
            if tracker is None:
                continue
            if kind == "translate":
                if err:
                    error = err
                    continue
                if tracker.text == text and english != tracker.english:
                    tracker.english = english
                    changed = True
                continue
            if err and not text:
                error = err
                tracker.retry_next()
                continue
            if err:
                error = err
            if tracker.accept_text(text):
                tracker.english = english
                changed = True
            elif text == tracker.text and english and english != tracker.english:
                tracker.english = english
                changed = True
        if changed:
            self._refresh_panel()
        if error:
            self.status.setText(error)
        else:
            self._set_status()
        if self._translate_after and not self._closing:
            self._translate_after = False
            self._request_translations()

    def _set_engine(self, text: str) -> None:
        self._engine = text
        self._set_status()

    def _set_status(self) -> None:
        parts = [self._engine or "OCR"]
        if self._picking:
            parts.append("click the game window, Esc cancels")
        elif self.bound_title:
            title = self.bound_title
            if len(title) > 42:
                title = title[:42] + "…"
            parts.append(title)
        else:
            parts.append("not bound")
        if self.pause_button.isChecked():
            parts.append("paused")
        self.status.setText("  ·  ".join(parts))

    def _refresh_panel(self) -> None:
        show_english = self.english_box.isChecked()
        use_ruby = self.furigana_box.isChecked() and self.furigana is not None
        spacing = self.spacing_box.isChecked() and self.furigana is not None
        want_dictionary = self.dictionary_box.isChecked() and self.dictionary.isVisible()
        multiple = len(self.regions) > 1
        sections = []
        collected = []
        for region in self.regions:
            tracker = self.trackers[region.region_id]
            text = tracker.text.strip()
            if not text:
                continue
            tokens = None
            if self.furigana is not None and (use_ruby or spacing or want_dictionary):
                tokens = self.furigana.tokens(text, spacing=spacing)
                collected.extend(tokens)
            display = tokens if (use_ruby or spacing) else None
            if display is not None and not use_ruby:
                for token in display:
                    token.reading = None
            sections.append(
                (
                    f"Region {region.index}" if multiple else "",
                    text,
                    display,
                    tracker.english.strip() if show_english else "",
                    use_ruby,
                )
            )
        self.panel.show_sections(sections)
        self._refresh_dictionary(collected)

    def _plain_text(self) -> str:
        chunks = []
        multiple = len(self.regions) > 1
        show_english = self.english_box.isChecked()
        for region in self.regions:
            tracker = self.trackers[region.region_id]
            text = tracker.text.strip()
            if not text:
                continue
            parts = []
            if multiple:
                parts.append(f"Region {region.index}")
            parts.append(text)
            if show_english and tracker.english.strip():
                parts.append(tracker.english.strip())
            chunks.append("\n".join(parts))
        return "\n\n".join(chunks)

    def _copy(self) -> None:
        QGuiApplication.clipboard().setText(self._plain_text())

    def _save(self) -> None:
        geometry = self.geometry()
        data = {
            "furigana": self.furigana_box.isChecked(),
            "spacing": self.spacing_box.isChecked(),
            "english": self.english_box.isChecked(),
            "paused": self.pause_button.isChecked(),
            "click_through": self.click_box.isChecked(),
            "hide_frames": self.hide_box.isChecked(),
            "dictionary": self.dictionary_box.isChecked(),
            "bound_title": self.bound_title,
            "window": {
                "x": geometry.x(),
                "y": geometry.y(),
                "w": geometry.width(),
                "h": geometry.height(),
            },
            "regions": [
                {
                    "x": region.geometry().x(),
                    "y": region.geometry().y(),
                    "w": region.geometry().width(),
                    "h": region.geometry().height(),
                    "rel": list(region.rel) if region.rel else None,
                }
                for region in self.regions
            ],
        }
        if self._dictionary_placed:
            placed = self.dictionary.geometry()
            data["dictionary_window"] = {
                "x": placed.x(),
                "y": placed.y(),
                "w": placed.width(),
                "h": placed.height(),
            }
        elif isinstance(self._saved.get("dictionary_window"), dict):
            data["dictionary_window"] = self._saved["dictionary_window"]
        config.save(data)

    def closeEvent(self, event) -> None:
        self._closing = True
        self._timer.stop()
        self._pick_timer.stop()
        self._save()
        for region in list(self.regions):
            region.close()
        self.dictionary.force_close()
        if self._dict_worker is not None:
            self._dict_worker.stop()
            self._dict_worker.wait(15000)
        self.worker.stop()
        self.worker.wait(15000)
        event.accept()
