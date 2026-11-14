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
from lisktranslate.furigana import Furigana, Token
from lisktranslate.ocr_engine import OcrService
from lisktranslate.panel import TextPanel
from lisktranslate.region import RegionFrame


class _Worker(QThread):
    status = Signal(str)
    batch_done = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self._queue: queue.Queue = queue.Queue()
        self.service: OcrService | None = None

    def submit(self, batch: list[tuple[int, object]]) -> None:
        self._queue.put(batch)

    def stop(self) -> None:
        self._queue.put(None)

    def run(self) -> None:
        try:
            self.service = OcrService()
            self.status.emit(self.service.status_line)
        except Exception as exc:
            self.status.emit(str(exc))
            self.service = None
        while True:
            batch = self._queue.get()
            if batch is None:
                return
            results = []
            for region_id, image in batch:
                if self.service is None or not self.service.available:
                    results.append((region_id, "", self.service.status_line if self.service else "OCR is unavailable."))
                    continue
                try:
                    results.append((region_id, self.service.recognize(image), ""))
                except Exception as exc:
                    results.append((region_id, "", str(exc)))
            engine = self.service.engine_name if self.service else "unavailable"
            self.batch_done.emit((results, engine))


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
        self._picking = False
        self._saw_click = False
        self._closing = False
        self._ticks = 0
        self._saved = config.load()
        self.furigana = self._load_furigana()
        self._build()
        self._restore()
        self.worker = _Worker()
        self.worker.status.connect(self._set_engine)
        self.worker.batch_done.connect(self._on_batch)
        self.worker.start()
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

        options = QHBoxLayout()
        self.furigana_box = QCheckBox("Furigana")
        self.furigana_box.setChecked(bool(self._saved.get("furigana", True)))
        if self.furigana is None:
            self.furigana_box.setChecked(False)
            self.furigana_box.setEnabled(False)
        self.click_box = QCheckBox("Click through")
        self.click_box.setChecked(bool(self._saved.get("click_through", False)))
        self.hide_box = QCheckBox("Hide frames")
        self.hide_box.setChecked(bool(self._saved.get("hide_frames", False)))
        self.furigana_box.toggled.connect(self._on_options)
        self.click_box.toggled.connect(self._on_options)
        self.hide_box.toggled.connect(self._on_options)
        options.addWidget(self.furigana_box)
        options.addWidget(self.click_box)
        options.addWidget(self.hide_box)
        options.addStretch(1)
        layout.addLayout(options)

        self.panel = TextPanel()
        layout.addWidget(self.panel, 1)

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
        self._engine = engine
        error = ""
        changed = False
        for region_id, text, err in results:
            tracker = self.trackers.get(region_id)
            if tracker is None:
                continue
            if err:
                error = err
                tracker.retry_next()
                continue
            if tracker.accept_text(text):
                changed = True
        if changed:
            self._refresh_panel()
        if error:
            self.status.setText(error)
        else:
            self._set_status()

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
        shown = [(region.index, self.trackers[region.region_id].text) for region in self.regions]
        shown = [(index, text) for index, text in shown if text.strip()]
        if not shown:
            self.panel.show_plain("")
            return
        multiple = len(self.regions) > 1
        if not self.furigana_box.isChecked() or self.furigana is None:
            chunks = []
            for index, text in shown:
                chunks.append(f"Region {index}\n{text}" if multiple else text)
            self.panel.show_plain("\n\n".join(chunks))
            return
        tokens: list[Token] = []
        for number, (index, text) in enumerate(shown):
            if number:
                tokens.append(Token("", break_line=True))
            if multiple:
                tokens.append(Token(f"Region {index}", header=True))
            tokens.extend(self.furigana.tokens(text))
        self.panel.show_ruby(tokens)

    def _plain_text(self) -> str:
        chunks = []
        multiple = len(self.regions) > 1
        for region in self.regions:
            text = self.trackers[region.region_id].text.strip()
            if not text:
                continue
            chunks.append(f"Region {region.index}\n{text}" if multiple else text)
        return "\n\n".join(chunks)

    def _copy(self) -> None:
        QGuiApplication.clipboard().setText(self._plain_text())

    def _save(self) -> None:
        geometry = self.geometry()
        config.save(
            {
                "furigana": self.furigana_box.isChecked(),
                "paused": self.pause_button.isChecked(),
                "click_through": self.click_box.isChecked(),
                "hide_frames": self.hide_box.isChecked(),
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
        )

    def closeEvent(self, event) -> None:
        self._closing = True
        self._timer.stop()
        self._pick_timer.stop()
        self._save()
        for region in list(self.regions):
            region.close()
        self.worker.stop()
        self.worker.wait(15000)
        event.accept()
