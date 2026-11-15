"""Japanese to English for the text panel."""

from __future__ import annotations

import json
import time
from html import unescape
from urllib.error import HTTPError
from urllib.request import Request, urlopen

_URL = "https://translate-pa.googleapis.com/v1/translateHtml"
_HEADERS = {
    "Accept": "*/*",
    "Content-Type": "application/json+protobuf",
    "X-Goog-Api-Key": "AIzaSyATBXajvzQLTDHEQbcpq0Ihe0vWDHmO520",
    "User-Agent": "Mozilla/5.0",
}
_last_request = 0.0


def _chunks(text: str, limit: int = 1800) -> list[str]:
    if len(text) <= limit:
        return [text]
    parts: list[str] = []
    chunk: list[str] = []
    size = 0
    for line in text.split("\n"):
        extra = len(line) + 1
        if chunk and size + extra > limit:
            parts.append("\n".join(chunk))
            chunk = []
            size = 0
        chunk.append(line)
        size += extra
    if chunk:
        parts.append("\n".join(chunk))
    return parts or [text]


def _post(texts: list[str]) -> list[str]:
    payload = json.dumps([[texts, "ja", "en"], "wt_lib"]).encode("utf-8")
    request = Request(_URL, data=payload, headers=_HEADERS, method="POST")
    try:
        with urlopen(request, timeout=8) as response:
            data = json.load(response)
    except HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code}") from exc
    lines = data[0] if isinstance(data, list) and data else None
    if not isinstance(lines, list) or len(lines) != len(texts):
        raise RuntimeError("The translation response was incomplete.")
    return [unescape(str(line or "")) for line in lines]


def _with_retry(post, texts: list[str], sleep=time.sleep) -> list[str]:
    delay = 0.8
    for attempt in range(3):
        try:
            return post(texts)
        except RuntimeError as exc:
            if "429" not in str(exc) or attempt == 2:
                raise
            sleep(delay)
            delay *= 2
    raise RuntimeError("HTTP 429")


def _pace() -> None:
    global _last_request
    wait = 0.4 - (time.monotonic() - _last_request)
    if wait > 0:
        time.sleep(wait)
    _last_request = time.monotonic()


def _google_batch(texts: list[str]) -> list[str]:
    _pace()
    return _with_retry(_post, texts)


class Translator:
    def __init__(self, translate=None) -> None:
        self._translate = translate or _google_batch
        self._cache: dict[str, str] = {}

    def english(self, text: str) -> str:
        return self.english_many([text])[0]

    def english_many(self, texts: list[str]) -> list[str]:
        results = [""] * len(texts)
        pending: dict[str, list[int]] = {}
        order: list[str] = []
        for index, text in enumerate(texts):
            key = text.strip()
            if not key:
                continue
            cached = self._cache.get(key)
            if cached is not None:
                results[index] = cached
                continue
            if key not in pending:
                pending[key] = []
                order.append(key)
            pending[key].append(index)
        if not order:
            return results
        pieces: list[str] = []
        spans: list[tuple[str, int]] = []
        for key in order:
            chunks = _chunks(key)
            spans.append((key, len(chunks)))
            pieces.extend(chunks)
        translated = self._translate(pieces)
        if len(translated) != len(pieces):
            raise RuntimeError("The translation response was incomplete.")
        cursor = 0
        for key, count in spans:
            value = "\n".join(translated[cursor : cursor + count]).strip()
            cursor += count
            self._cache[key] = value
            for index in pending[key]:
                results[index] = value
        return results
