"""MeCab readings for recognized Japanese text."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Token:
    surface: str
    reading: str | None = None
    break_line: bool = False
    header: bool = False


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

    def tokens(self, text: str) -> list[Token]:
        tokens: list[Token] = []
        for index, line in enumerate(text.split("\n")):
            if index:
                tokens.append(Token("", break_line=True))
            for word in self._tagger(line):
                surface = word.surface
                if not surface:
                    continue
                kana = getattr(word.feature, "kana", None)
                reading = None
                if kana and kana != "*":
                    reading = _hide_reading(surface, kata_to_hira(str(kana)))
                tokens.append(Token(surface, reading))
        return tokens
