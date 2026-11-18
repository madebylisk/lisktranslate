"""Plain-text history, one file per region, grouped so a day stays easy to browse."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

_INVALID = '<>:"/\\|?*'


def safe_name(text: str, fallback: str) -> str:
    cleaned = []
    for char in text.strip():
        if char in _INVALID or ord(char) < 32:
            cleaned.append(" ")
        else:
            cleaned.append(char)
    name = " ".join("".join(cleaned).split()).rstrip(". ")
    if not name:
        return fallback
    return name[:80]


def history_path(root: Path, group: str, region: str, when: datetime) -> Path:
    month = when.strftime("%Y-%m")
    day = when.strftime("%Y-%m-%d")
    return root / safe_name(group, "General") / month / day / f"{safe_name(region, 'Region')}.txt"


def _render(entries: list[tuple[datetime, str, str, str]], separate: bool) -> str:
    parts: list[str] = []
    for index, (when, japanese, english, furigana) in enumerate(entries):
        if separate or index:
            parts.append("---\n\n")
        parts.append(when.strftime("%H:%M:%S"))
        parts.append("\n\n")
        parts.append((furigana or japanese).strip())
        parts.append("\n")
        if english.strip():
            parts.append("\n")
            parts.append(english.strip())
            parts.append("\n")
        parts.append("\n")
    return "".join(parts)


class HistoryLog:
    def __init__(self, root: Path | None = None, now=None) -> None:
        self.root = root
        self._now = now or datetime.now
        self._prefix: dict[Path, str] = {}
        self._session: dict[tuple[str, str, str], list[tuple[datetime, str, str, str]]] = {}

    def set_root(self, root: Path | None) -> None:
        self.root = root
        self._prefix.clear()
        for key in self._session:
            self._write(key)

    def add(self, group: str, region: str, japanese: str, english: str, furigana: str = "") -> None:
        japanese = japanese.strip()
        if not japanese:
            return
        when = self._now()
        key = (safe_name(group, "General"), when.strftime("%Y-%m-%d"), safe_name(region, "Region"))
        rows = self._session.setdefault(key, [])
        english = english.strip()
        furigana = furigana.strip()
        if furigana == japanese:
            furigana = ""
        if rows and rows[-1][1] == japanese:
            changed = False
            if english and rows[-1][2] != english:
                english_text = english
                changed = True
            else:
                english_text = rows[-1][2]
            if furigana and rows[-1][3] != furigana:
                changed = True
            else:
                furigana = rows[-1][3]
            if changed:
                rows[-1] = (rows[-1][0], japanese, english_text, furigana)
                self._write(key)
            return
        rows.append((when, japanese, english, furigana))
        self._write(key)

    def set_english(self, group: str, region: str, japanese: str, english: str) -> None:
        japanese = japanese.strip()
        english = english.strip()
        if not japanese or not english:
            return
        group_name = safe_name(group, "General")
        region_name = safe_name(region, "Region")
        matches = [key for key in self._session if key[0] == group_name and key[2] == region_name]
        if not matches:
            return
        key = sorted(matches)[-1]
        rows = self._session[key]
        for index in range(len(rows) - 1, -1, -1):
            when, text, old, furigana = rows[index]
            if text == japanese and old != english:
                rows[index] = (when, text, english, furigana)
                self._write(key)
                return

    def _write(self, key: tuple[str, str, str]) -> None:
        rows = self._session.get(key) or []
        if self.root is None or not rows:
            return
        when = rows[0][0]
        path = self.root / key[0] / when.strftime("%Y-%m") / key[1] / f"{key[2]}.txt"
        if path not in self._prefix:
            existing = ""
            if path.is_file():
                existing = path.read_text(encoding="utf-8")
                if existing and not existing.endswith("\n"):
                    existing += "\n"
            self._prefix[path] = existing
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self._prefix[path] + _render(rows, separate=bool(self._prefix[path])), encoding="utf-8")
