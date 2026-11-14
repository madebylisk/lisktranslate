"""Sort OCR boxes into reading order and join them into dialogue."""

from __future__ import annotations

import math


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
    merged = _merge_nearby(cleaned, vertical, space)
    lines = sort_lines(
        [box for _, box in merged],
        [text for text, _ in merged],
        vertical,
        space,
    )
    return "\n".join(text for text, _ in lines if text)
