"""Offline JMdict and KANJIDIC lookups for the current text."""

from __future__ import annotations

import lzma
import os
import shutil
import tarfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path

_DATA_URL = (
    "https://files.pythonhosted.org/packages/97/a5/"
    "075928aed2b3b70459fc1db396397dfa6714d266c143c51af9b648551a4e/"
    "jamdict_data-1.5.tar.gz"
)
_SKIP_POS = {"補助記号", "空白", "記号", "助詞"}


@dataclass(frozen=True)
class WordGloss:
    written: str
    reading: str
    meanings: str


@dataclass(frozen=True)
class KanjiGloss:
    character: str
    readings: str
    meanings: str


@dataclass(frozen=True)
class DictionaryPage:
    words: tuple[WordGloss, ...]
    kanji: tuple[KanjiGloss, ...]


def dictionary_path() -> Path:
    root = os.environ.get("LOCALAPPDATA") or str(Path.home())
    folder = Path(root) / "lisktranslate"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "jamdict.db"


def dictionary_ready() -> bool:
    path = dictionary_path()
    return path.is_file() and path.stat().st_size > 5_000_000


def ensure_dictionary(status=None) -> Path:
    path = dictionary_path()
    if dictionary_ready():
        return path
    partial = path.with_suffix(".db.partial")
    archive_path = path.with_suffix(".tar.gz")
    try:
        if status:
            status("Downloading the offline dictionary…")
        request = urllib.request.Request(_DATA_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=120) as response, archive_path.open("wb") as handle:
            shutil.copyfileobj(response, handle)
        if status:
            status("Preparing the offline dictionary…")
        with tarfile.open(archive_path, "r:gz") as archive:
            member = next(item for item in archive.getmembers() if item.name.endswith("jamdict.db.xz"))
            extracted = archive.extractfile(member)
            if extracted is None:
                raise RuntimeError("The dictionary archive had no database.")
            with lzma.open(extracted) as compressed, partial.open("wb") as handle:
                shutil.copyfileobj(compressed, handle)
        partial.replace(path)
    except Exception:
        partial.unlink(missing_ok=True)
        raise
    finally:
        archive_path.unlink(missing_ok=True)
    if not dictionary_ready():
        path.unlink(missing_ok=True)
        raise RuntimeError("The dictionary download was incomplete.")
    return path


def has_kanji(text: str) -> bool:
    return any(0x3400 <= ord(ch) <= 0x9FFF for ch in text)


def clean_lemma(lemma: str) -> str:
    lemma = (lemma or "").strip()
    if not lemma or lemma == "*":
        return ""
    if "-" in lemma:
        left, right = lemma.split("-", 1)
        if left and right and not has_kanji(right):
            return left
    return lemma


def headword(token) -> str:
    if getattr(token, "break_line", False) or getattr(token, "header", False):
        return ""
    if not getattr(token, "surface", ""):
        return ""
    lemma = clean_lemma(getattr(token, "lemma", "")) or token.surface
    if getattr(token, "pos", "") in _SKIP_POS and not has_kanji(token.surface):
        return ""
    if has_kanji(lemma):
        return lemma
    if has_kanji(token.surface):
        return token.surface
    return ""


def _forms(entry) -> tuple[list[str], list[str]]:
    kanji = [form.text for form in entry.kanji_forms if getattr(form, "text", "")]
    kana = [form.text for form in entry.kana_forms if getattr(form, "text", "")]
    return kanji, kana


def _common(entry) -> bool:
    for form in list(entry.kanji_forms) + list(entry.kana_forms):
        if getattr(form, "pri", None):
            return True
    return False


def _sense_applies(sense, written: str, reading: str) -> bool:
    written_only = [item for item in (getattr(sense, "stagk", None) or []) if item]
    reading_only = [item for item in (getattr(sense, "stagr", None) or []) if item]
    if written_only and written not in written_only:
        return False
    if reading_only and reading not in reading_only:
        return False
    return True


def _english_senses(entry, written: str = "", reading: str = "", limit: int = 3) -> str:
    matched = _collect_senses(entry, written, reading, limit, restricted=True)
    if matched:
        return matched
    return _collect_senses(entry, written, reading, limit, restricted=False)


def _collect_senses(entry, written: str, reading: str, limit: int, restricted: bool) -> str:
    parts: list[str] = []
    for sense in entry.senses:
        if restricted and not _sense_applies(sense, written, reading):
            continue
        words = []
        for gloss in getattr(sense, "gloss", []):
            lang = (getattr(gloss, "lang", None) or "eng").lower()
            if lang not in {"eng", "en", ""}:
                continue
            text = (getattr(gloss, "text", "") or "").strip()
            if text:
                words.append(text)
        kinds = [item for item in (getattr(sense, "name_type", None) or []) if item]
        if kinds and words:
            parts.append(f"{', '.join(kinds)}: {', '.join(words[:4])}")
        elif kinds:
            parts.append(", ".join(kinds))
        elif words:
            parts.append(", ".join(words[:4]))
        if len(parts) >= limit:
            break
    return "; ".join(parts)


def format_word(entry, query: str, reading: str) -> WordGloss | None:
    kanji, kana = _forms(entry)
    if query not in kanji and query not in kana:
        return None
    if query in kanji:
        written = query
    elif kanji:
        written = kanji[0]
    else:
        written = kana[0] if kana else query
    if reading and reading in kana:
        shown = reading
    elif kana:
        shown = kana[0]
    else:
        shown = reading
    meanings = _english_senses(entry, written, shown)
    if not meanings:
        return None
    return WordGloss(written, shown, meanings)


def pick_word(entries, query: str, reading: str) -> WordGloss | None:
    ranked = []
    for entry in entries:
        gloss = format_word(entry, query, reading)
        if gloss is None:
            continue
        ranked.append((0 if gloss.reading == reading else 1, 0 if _common(entry) else 1, gloss))
    if not ranked:
        return None
    ranked.sort(key=lambda item: (item[0], item[1]))
    return ranked[0][2]


def format_kanji(char) -> KanjiGloss | None:
    if char is None:
        return None
    literal = getattr(char, "literal", "") or getattr(char, "text", "")
    if not literal:
        return None
    kun: list[str] = []
    on: list[str] = []
    for group in getattr(char, "rm_groups", []):
        for reading in group.readings:
            value = (reading.value or "").strip()
            if not value or value.startswith("-") or value.endswith("-"):
                continue
            if reading.r_type == "ja_kun" and value not in kun:
                kun.append(value)
            elif reading.r_type == "ja_on" and value not in on:
                on.append(value)
    meanings = ", ".join(char.meanings(english_only=True)[:6])
    readings = "、".join(kun[:4] + on[:3])
    if not meanings and not readings:
        return None
    return KanjiGloss(literal, readings, meanings)


class Dictionary:
    def __init__(self, jam=None) -> None:
        self._jam = jam if jam is not None else _open_jam()
        self._words: dict[tuple[str, str], WordGloss | None] = {}
        self._kanji: dict[str, KanjiGloss | None] = {}

    def explain(self, tokens) -> DictionaryPage:
        words: list[WordGloss] = []
        seen: set[str] = set()
        characters: list[str] = []
        seen_kanji: set[str] = set()
        for token in tokens:
            surface = getattr(token, "surface", "") or ""
            for ch in surface:
                if has_kanji(ch) and ch not in seen_kanji:
                    seen_kanji.add(ch)
                    characters.append(ch)
            query = headword(token)
            if not query or query in seen:
                continue
            seen.add(query)
            gloss = self._word(query, getattr(token, "kana", "") or "")
            if gloss is not None:
                words.append(gloss)
        kanji = [item for item in (self._character(ch) for ch in characters) if item is not None]
        return DictionaryPage(tuple(words), tuple(kanji))

    def _word(self, query: str, reading: str) -> WordGloss | None:
        key = (query, reading)
        if key in self._words:
            return self._words[key]
        result = self._jam.lookup(query, lookup_chars=False, lookup_ne=False)
        gloss = pick_word(result.entries, query, reading)
        if gloss is None:
            named = self._jam.lookup(query, lookup_chars=False, lookup_ne=True)
            gloss = pick_word(named.names, query, reading)
        self._words[key] = gloss
        return gloss

    def _character(self, character: str) -> KanjiGloss | None:
        if character in self._kanji:
            return self._kanji[character]
        gloss = format_kanji(self._jam.get_char(character))
        self._kanji[character] = gloss
        return gloss


def _open_jam():
    from jamdict import Jamdict

    path = ensure_dictionary()
    return Jamdict(db_file=str(path), reuse_ctx=True)
