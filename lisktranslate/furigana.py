"""MeCab readings for recognized Japanese text."""

from __future__ import annotations

from dataclasses import dataclass


WORD_GAP = 8
_GRAMMAR = {"助詞", "助動詞"}
_OPENERS = set("「『（([【〈《｛{")
_CLOSERS = set("」』）)]】〉》｝}、。！？!?…・,.，．")


@dataclass
class Token:
    surface: str
    reading: str | None = None
    break_line: bool = False
    header: bool = False
    gap_before: int = 0
    lemma: str = ""
    pos: str = ""
    kana: str = ""
    grammar: bool = False
    muted: bool = False


def with_readings(tokens: list[Token]) -> str:
    """The sentence with a reading after each kanji word, like 今日（きょう）."""
    parts: list[str] = []
    for token in tokens:
        if token.break_line:
            parts.append("\n")
            continue
        parts.append(token.surface)
        if token.reading:
            parts.append(f"（{token.reading}）")
    return "".join(parts).strip()


def kata_to_hira(text: str) -> str:
    chars = []
    for ch in text:
        code = ord(ch)
        if 0x30A1 <= code <= 0x30F6:
            chars.append(chr(code - 0x60))
        else:
            chars.append(ch)
    return "".join(chars)


def _hide_reading(surface: str, reading: str | None) -> str | None:
    if not reading or reading == surface or surface.isascii():
        return None
    if all(_is_kana_or_mark(ch) for ch in surface):
        return None
    return reading


def _is_kana_or_mark(ch: str) -> bool:
    code = ord(ch)
    if 0x3040 <= code <= 0x30FF:
        return True
    return ch in "、。！？!?…・「」『』（）()[]【】　 "


class Furigana:
    def __init__(self) -> None:
        import fugashi
        import unidic_lite

        self._tagger = fugashi.Tagger('-r nul -d "{}"'.format(unidic_lite.DICDIR))

    def tokens(self, text: str, spacing: bool = False) -> list[Token]:
        tokens: list[Token] = []
        for index, line in enumerate(text.split("\n")):
            if index:
                tokens.append(Token("", break_line=True))
            for word in self._tagger(line):
                surface = word.surface
                if not surface:
                    continue
                feature = word.feature
                kana = getattr(feature, "kana", None)
                hiragana = ""
                reading = None
                if kana and str(kana) != "*":
                    hiragana = kata_to_hira(str(kana))
                    reading = _hide_reading(surface, hiragana)
                pos = str(getattr(feature, "pos1", "") or "")
                lemma = str(getattr(feature, "lemma", "") or "")
                if lemma == "*":
                    lemma = ""
                tokens.append(
                    Token(
                        surface,
                        reading,
                        lemma=lemma,
                        pos=pos,
                        kana=hiragana,
                        grammar=pos in _GRAMMAR,
                    )
                )
        if spacing:
            _apply_spacing(tokens)
        return tokens


def _apply_spacing(tokens: list[Token]) -> None:
    previous: Token | None = None
    for token in tokens:
        if token.break_line or token.header:
            previous = None
            continue
        token.gap_before = _gap(previous, token)
        token.muted = token.grammar
        previous = token


def _glue(token: Token) -> bool:
    return token.grammar or token.pos == "接尾辞"


def _gap(previous: Token | None, token: Token) -> int:
    if previous is None:
        return 0
    if token.surface and all(ch in _CLOSERS for ch in token.surface):
        return 0
    if previous.surface and all(ch in _OPENERS for ch in previous.surface):
        return 0
    if previous.pos == "接頭辞":
        return 0
    if _glue(previous) and _glue(token):
        return 0
    if previous.pos == "動詞" and token.lemma == "ます":
        return 0
    return WORD_GAP
