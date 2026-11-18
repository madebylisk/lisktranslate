"""Sort OCR boxes into reading order and join them into dialogue."""

from __future__ import annotations

import math
import threading


Box = tuple[float, float, float, float]
Line = tuple[str, Box]


def guess_vertical(boxes: list[Box]) -> bool:
    """Luna's check: a product of width/height below 1 means vertical text."""
    product = 1.0
    used = False
    for x1, y1, x2, y2 in boxes:
        width = x2 - x1
        height = y2 - y1
        if width == 0 or height == 0:
            continue
        product *= width / height
        used = True
    return used and product < 1


def _mostly_cjk(text: str) -> bool:
    letters = [ch for ch in text if not ch.isspace()]
    if not letters:
        return True
    cjk = 0
    for ch in letters:
        code = ord(ch)
        if (
            0x3040 <= code <= 0x30FF
            or 0x3400 <= code <= 0x9FFF
            or 0xF900 <= code <= 0xFAFF
        ):
            cjk += 1
    return cjk * 2 >= len(letters)


def _distance(a: Box, b: Box) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    if ax1 <= bx2 and ax2 >= bx1 and ay1 <= by2 and ay2 >= by1:
        return 0.0
    if ax2 < bx1:
        dx = bx1 - ax2
    elif bx2 < ax1:
        dx = ax1 - bx2
    else:
        dx = 0.0
    if ay2 < by1:
        dy = by1 - ay2
    elif by2 < ay1:
        dy = ay1 - by2
    else:
        dy = 0.0
    return math.hypot(dx, dy)


def _whmin(box: Box) -> float:
    x1, y1, x2, y2 = box
    return min(x2 - x1, y2 - y1)


def sort_lines(boxes: list[Box], texts: list[str], vertical: bool, space: str) -> list[Line]:
    """Group boxes into visual lines. Within a line, join with `space`."""
    if not boxes:
        return []
    axis = 0 if vertical else 1
    other = 1 - axis
    mids = [((box[0] + box[2]) / 2, (box[1] + box[3]) / 2) for box in boxes]
    spans = [((box[0], box[2]), (box[1], box[3])) for box in boxes]
    used = [False] * len(boxes)
    groups: list[list[int]] = []
    for i in range(len(boxes)):
        if used[i]:
            continue
        group = [i]
        used[i] = True
        mi = mids[i][axis]
        ri_min, ri_max = spans[i][axis]
        for j in range(i + 1, len(boxes)):
            if used[j]:
                continue
            mj = mids[j][axis]
            rj_min, rj_max = spans[j][axis]
            if mi > rj_min and mi < rj_max and mj > ri_min and mj < ri_max:
                used[j] = True
                group.append(j)
        groups.append(group)
    for group in groups:
        group.sort(key=lambda index: mids[index][other])
    groups.sort(key=lambda group: mids[group[0]][axis], reverse=vertical)
    lines: list[Line] = []
    for group in groups:
        text = space.join(texts[index] for index in group)
        box = (
            min(spans[index][0][0] for index in group),
            min(spans[index][1][0] for index in group),
            max(spans[index][0][1] for index in group),
            max(spans[index][1][1] for index in group),
        )
        lines.append((text, box))
    return lines


def join_lines(lines: list[Line], vertical: bool, space: str) -> str:
    """Join wrapped lines. A short line that does not reach the next edge stays separate."""
    parts: list[str] = []
    prev: Box | None = None
    for text, box in lines:
        if prev is not None:
            if vertical:
                tol = min(prev[2] - prev[0], box[2] - box[0])
                sep = "\n" if prev[3] < box[3] - tol else space
            else:
                tol = min(prev[3] - prev[1], box[3] - box[1])
                sep = "\n" if prev[2] < box[2] - tol else space
            parts.append(sep)
        parts.append(text)
        prev = box
    return "".join(parts)


def _union(boxes: list[Box]) -> Box:
    return (
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    )


def _merge_nearby(items: list[Line], vertical: bool, space: str, gap_ratio: float = 0.4) -> list[Line]:
    groups: list[list[Line]] = [[item] for item in items]
    if not groups:
        return []

    def gap(a: list[Line], b: list[Line]) -> float:
        best = math.inf
        for _, box_a in a:
            for _, box_b in b:
                best = min(best, _distance(box_a, box_b))
                if best == 0:
                    return 0.0
        return best

    def weight(group: list[Line]) -> float:
        return sum(_whmin(box) for _, box in group) / len(group)

    matrix = [[0.0] * len(groups) for _ in groups]
    for i in range(len(groups)):
        for j in range(i + 1, len(groups)):
            matrix[i][j] = matrix[j][i] = gap(groups[i], groups[j])

    i = 0
    while i < len(groups):
        merged = False
        j = 0
        while j < len(groups):
            if i == j:
                j += 1
                continue
            threshold = gap_ratio * min(weight(groups[i]), weight(groups[j]))
            if matrix[i][j] <= threshold:
                groups[i].extend(groups.pop(j))
                matrix.pop(j)
                for row in matrix:
                    row.pop(j)
                for k in range(len(groups)):
                    if i != k:
                        matrix[i][k] = matrix[k][i] = gap(groups[i], groups[k])
                if j < i:
                    i -= 1
                j = 0
                merged = True
            else:
                j += 1
        if not merged:
            i += 1

    merged_lines: list[Line] = []
    for group in groups:
        boxes = [box for _, box in group]
        texts = [text for text, _ in group]
        lines = sort_lines(boxes, texts, vertical, space)
        merged_lines.append((join_lines(lines, vertical, space), _union(boxes)))
    return merged_lines


def _is_nameplate(text: str) -> bool:
    """A short speaker label, not the start of a sentence."""
    text = "".join(text.split())
    if not text or len(text) > 8:
        return False
    if any(ch in "。！？、,.!?…・" for ch in text):
        return False
    named = False
    for ch in text:
        code = ord(ch)
        if 0x30A0 <= code <= 0x30FF or 0x3400 <= code <= 0x9FFF or 0xF900 <= code <= 0xFAFF:
            named = True
            continue
        if 0x3040 <= code <= 0x309F or ch in "々〆ヶ":
            continue
        return False
    return named


def _peel_nameplate(items: list[Line]) -> tuple[str, list[Line]]:
    """Drop a speaker label that sits above the dialogue, like a nameplate."""
    if len(items) < 2:
        return "", items
    ordered = sorted(items, key=lambda item: (item[1][1], item[1][0]))
    text, box = ordered[0]
    if not _is_nameplate(text):
        return "", items
    below = [item for item in ordered[1:] if (item[1][1] + item[1][3]) / 2 > box[3]]
    if not below:
        return "", items
    height = box[3] - box[1]
    gap = min(other[1] for _, other in below) - box[3]
    if height <= 0 or gap < 0.4 * height:
        return "", items
    left = min(other[0] for _, other in below)
    right = max(other[2] for _, other in below)
    width = right - left
    name_width = box[2] - box[0]
    if width <= 0 or name_width > 0.55 * width:
        return "", items
    mid = (box[0] + box[2]) / 2
    if mid < left - height or mid > right + height:
        return "", items
    body = "".join(part for part, _ in ordered[1:])
    if len(body) < len(text) + 4 or not _has_sentence_end(body):
        return "", items
    return text, ordered[1:]


_tagger = None
_tagger_lock = threading.Lock()
_ATTACHED = ("から", "まで", "より", "って", "ので", "のに", "のが", "のを", "のは", "のも")


def _words(text: str):
    """Tokenize with the same dictionary furigana uses. None if it cannot load."""
    global _tagger
    with _tagger_lock:
        if _tagger is False:
            return None
        if _tagger is None:
            try:
                import fugashi
                import unidic_lite

                _tagger = fugashi.Tagger('-r nul -d "{}"'.format(unidic_lite.DICDIR))
            except Exception:
                _tagger = False
                return None
        return list(_tagger(text))


def _is_katakana(text: str) -> bool:
    return len(text) >= 2 and all(0x30A0 <= ord(ch) <= 0x30FF for ch in text)


def _has_sentence_end(text: str) -> bool:
    """A line can end with a period, a question, or an ellipsis like .... or ……."""
    if any(ch in text for ch in "。！？!?…‥"):
        return True
    run = 0
    for ch in text:
        if ch in ".．・･":
            run += 1
            if run >= 2:
                return True
        else:
            run = 0
    return False


def _is_speaker_noun(text: str) -> bool:
    """A name standing alone, not a verb, a particle phrase, or a word like 今日."""
    words = _words(text)
    if not words or "".join(word.surface for word in words) != text:
        return False
    # An unknown katakana name is often cut into ordinary words, as ロクロウ becomes ロク and ロウ.
    if _is_katakana(text) and len(words) >= 2:
        return all(str(getattr(word.feature, "pos1", "") or "") == "名詞" for word in words)
    saw_noun = False
    for word in words:
        feature = word.feature
        pos1 = str(getattr(feature, "pos1", "") or "")
        pos2 = str(getattr(feature, "pos2", "") or "")
        pos3 = str(getattr(feature, "pos3", "") or "")
        if pos1 == "接頭辞":
            if word.surface not in {"お", "ご", "御"}:
                return False
            continue
        if pos1 == "接尾辞" and pos2 == "名詞的":
            continue
        if pos1 == "名詞" and (pos2 == "固有名詞" or pos3 == "一般"):
            saw_noun = True
            continue
        return False
    return saw_noun


def _attaches(body: str) -> bool:
    """The next line continues the name, as in 今日 / はいい天気."""
    rest = body.lstrip()
    if not rest:
        return True
    first = rest[0]
    if first in "はがをにとへや":
        return True
    if first == "の" and (len(rest) == 1 or not ("\u3041" <= rest[1] <= "\u3096")):
        return True
    return rest.startswith(_ATTACHED)


def _first_line(text: str) -> str:
    for part in text.split("\n"):
        part = "".join(part.split())
        if part:
            return part
    return ""


def _split_leading_name(text: str) -> tuple[str, str]:
    """A short name on its own line is the speaker, even without a wide gap above the line."""
    line, sep, body = text.partition("\n")
    if not sep or not body.strip():
        return "", text
    name = "".join(line.split())
    if name != line.strip() or not _is_nameplate(name) or _attaches(body):
        return "", text
    dialogue = "".join(body.split())
    if len(dialogue) < max(12, len(name) + 8) or not _has_sentence_end(dialogue):
        return "", text
    if len(_first_line(body)) <= len(name):
        return "", text
    if not _is_speaker_noun(name):
        return "", text
    return name, body


def split_speaker(text: str) -> tuple[str, str]:
    """Split a speaker name off the dialogue. Other text is returned unchanged."""
    if text.startswith("\x1e"):
        speaker, sep, body = text[1:].partition("\n")
        if not sep or not body.strip():
            return "", text
        return speaker.strip(), body
    return _split_leading_name(text)


def assemble(items: list[Line], *, vertical: bool | None = None, space: str | None = None) -> str:
    """Turn OCR fragments into one string, in reading order."""
    cleaned: list[Line] = []
    for text, box in items:
        if not text or not str(text).strip():
            continue
        x1, y1, x2, y2 = box
        if x2 < x1:
            x1, x2 = x2, x1
        if y2 < y1:
            y1, y2 = y2, y1
        cleaned.append((str(text).strip(), (x1, y1, x2, y2)))
    if not cleaned:
        return ""
    if space is None:
        space = "" if _mostly_cjk("".join(text for text, _ in cleaned)) else " "
    if vertical is None:
        vertical = guess_vertical([box for _, box in cleaned])
    speaker = ""
    working = cleaned
    if not vertical:
        speaker, working = _peel_nameplate(working)
    merged = _merge_nearby(working, vertical, space)
    lines = sort_lines(
        [box for _, box in merged],
        [text for text, _ in merged],
        vertical,
        space,
    )
    body = "\n".join(text for text, _ in lines if text)
    if speaker and body:
        return f"\x1e{speaker}\n{body}"
    return body
