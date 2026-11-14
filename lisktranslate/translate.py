"""Japanese to English for the text panel."""

from __future__ import annotations

import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def _google(text: str) -> str:
    query = urlencode(
        {"client": "gtx", "sl": "ja", "tl": "en", "dt": "t", "q": text}
    )
    request = Request(
        "https://translate.googleapis.com/translate_a/single?" + query,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    with urlopen(request, timeout=8) as response:
        data = json.load(response)
    return "".join(part[0] for part in data[0] if part and part[0])


class Translator:
    def __init__(self, translate=None) -> None:
        self._translate = translate or _google
        self._cache: dict[str, str] = {}

    def english(self, text: str) -> str:
        key = text.strip()
        if not key:
            return ""
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        translated = self._translate_long(key).strip()
        self._cache[key] = translated
        return translated

    def _translate_long(self, text: str) -> str:
        if len(text) <= 1800:
            return self._translate(text) or ""
        parts: list[str] = []
        chunk: list[str] = []
        size = 0
        for line in text.split("\n"):
            extra = len(line) + 1
            if chunk and size + extra > 1800:
                parts.append(self._translate("\n".join(chunk)) or "")
                chunk = []
                size = 0
            chunk.append(line)
            size += extra
        if chunk:
            parts.append(self._translate("\n".join(chunk)) or "")
        return "\n".join(parts)
