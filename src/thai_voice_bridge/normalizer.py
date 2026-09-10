"""Offline Thai spoken numeral and entity pronunciation normalizer."""

from __future__ import annotations

import re

_DIGIT_VALUES: dict[str, int] = {
    "ศูนย์": 0,
    "หนึ่ง": 1,
    "เอ็ด": 1,
    "สอง": 2,
    "ยี่": 2,
    "สาม": 3,
    "สี่": 4,
    "ห้า": 5,
    "หก": 6,
    "เจ็ด": 7,
    "แปด": 8,
    "เก้า": 9,
}

_UNIT_VALUES: dict[str, int] = {
    "สิบ": 10,
    "ร้อย": 100,
    "พัน": 1000,
    "หมื่น": 10_000,
    "แสน": 100_000,
    "ล้าน": 1_000_000,
}

_NUMBER_WORDS: tuple[str, ...] = tuple(
    sorted(
        (*_DIGIT_VALUES.keys(), *_UNIT_VALUES.keys()),
        key=len,
        reverse=True,
    )
)

_CURRENCY_UNITS = ("บาท", "สตางค์")
_TIME_MOONG = "โมง"
_TIME_THUM = "ทุ่ม"
_TIME_MODIFIERS = ("เช้า", "เย็น", "บ่าย", "ตรง", "ครึ่ง")

_WHITESPACE_RE = re.compile(r"\s+")


def parse_thai_number(text: str) -> int | None:
    """Parse a Thai spoken number phrase into an int, or None if invalid."""
    compact = _WHITESPACE_RE.sub("", (text or "").strip())
    if not compact:
        return None
    tokens = _consume_number_tokens(compact, 0)
    if tokens is None:
        return None
    end, values = tokens
    if end != len(compact) or not values:
        return None
    return _compose_number(values)


def normalize_spoken_text(text: str) -> str:
    """Normalize spoken Thai numerals and common entities to Arabic forms."""
    raw = _WHITESPACE_RE.sub(" ", (text or "").strip())
    if not raw:
        return ""

    # Scan a spaceless copy for number/entity spans, but splice replacements
    # back into the spaced original so wake phrases and Thai wording stay intact.
    compact = raw.replace(" ", "")
    space_map = _build_space_index_map(raw)

    out_parts: list[str] = []
    last_raw = 0
    i = 0
    n = len(compact)

    while i < n:
        afternoon = False
        afternoon_start = i
        if compact.startswith("บ่าย", i):
            look = _try_match_entity(compact, i + len("บ่าย"))
            if look is not None and look[2][0] == "time_moong":
                afternoon = True
                i += len("บ่าย")
            else:
                i += len("บ่าย")
                continue

        matched = _try_match_entity(compact, i)
        if matched is None:
            i += 1
            continue

        end, rendered, _meta = matched
        if afternoon:
            rendered = _shift_moong_afternoon(rendered)
            span_start = afternoon_start
        else:
            span_start = i

        raw_start = space_map[span_start]
        raw_end = space_map[end - 1] + 1 if end > span_start else space_map[span_start]
        # Include any trailing spaces consumed only in compact form — raw_end
        # already points past the last compact char's raw index.
        out_parts.append(raw[last_raw:raw_start])
        out_parts.append(rendered)
        last_raw = raw_end
        # Skip spaces that sat between the entity and the next token in raw.
        while last_raw < len(raw) and raw[last_raw] == " ":
            # Keep a single boundary space only when the next raw char is Thai
            # and the rendered form does not already end with a space/unit gap.
            break
        i = end

    out_parts.append(raw[last_raw:])
    return _cleanup_spacing("".join(out_parts))


def _build_space_index_map(raw: str) -> list[int]:
    """Map each index in spaceless compact form → index in spaced raw."""
    mapping: list[int] = []
    for idx, ch in enumerate(raw):
        if ch != " ":
            mapping.append(idx)
    return mapping


def _try_match_entity(
    compact: str, start: int
) -> tuple[int, str, tuple[str, ...]] | None:
    consumed = _consume_number_tokens(compact, start)
    if consumed is None:
        return None
    end, values = consumed
    if not values:
        return None

    number = _compose_number(values)
    digit_only = all(kind == "digit" for kind, _ in values)

    if digit_only and len(values) >= 9:
        digits = "".join(str(v) for _, v in values)
        return end, digits, ("phone",)

    for unit in _CURRENCY_UNITS:
        if compact.startswith(unit, end):
            return end + len(unit), f"{number} {unit}", ("currency", unit)

    if compact.startswith(_TIME_MOONG, end):
        end2 = end + len(_TIME_MOONG)
        hour = number
        trailing = ""
        for mod in _TIME_MODIFIERS:
            if compact.startswith(mod, end2):
                if mod == "เย็น" and hour < 12:
                    hour += 12
                trailing = f" {mod}"
                end2 += len(mod)
                break
        return end2, f"{hour}:00 {_TIME_MOONG}{trailing}", ("time_moong",)

    if compact.startswith(_TIME_THUM, end):
        hour = 18 + number if number >= 1 else 18
        return end + len(_TIME_THUM), f"{hour}:00 {_TIME_THUM}", ("time_thum",)

    return end, str(number), ("number",)


def _consume_number_tokens(
    compact: str, start: int
) -> tuple[int, list[tuple[str, int]]] | None:
    i = start
    values: list[tuple[str, int]] = []
    words: list[str] = []
    while i < len(compact):
        matched = _match_number_word(compact, i)
        if matched is None:
            break
        token, length = matched
        words.append(token)
        if token in _DIGIT_VALUES:
            values.append(("digit", _DIGIT_VALUES[token]))
        else:
            values.append(("unit", _UNIT_VALUES[token]))
        i += length
    if not values:
        return None
    if words == ["ยี่"]:
        return None
    return i, values


def _match_number_word(compact: str, start: int) -> tuple[str, int] | None:
    for word in _NUMBER_WORDS:
        if compact.startswith(word, start):
            return word, len(word)
    return None


def _compose_number(values: list[tuple[str, int]]) -> int:
    total = 0
    group = 0
    current = 0

    for kind, value in values:
        if kind == "digit":
            current = value
            continue

        unit = value
        if unit == 1_000_000:
            add = group + current
            if add == 0:
                add = 1
            total += add * unit
            group = 0
            current = 0
            continue

        coeff = current if current != 0 else 1
        group += coeff * unit
        current = 0

    return total + group + current


def _shift_moong_afternoon(rendered: str) -> str:
    try:
        hour_s, rest = rendered.split(":", 1)
        hour = int(hour_s)
        if hour < 12:
            hour += 12
        return f"{hour}:{rest}"
    except ValueError:
        return rendered


def _cleanup_spacing(text: str) -> str:
    """Insert spaces at Thai/Latin/digit boundaries and collapse whitespace."""
    if not text:
        return ""

    text = re.sub(r"([ก-๙])(\d)", r"\1 \2", text)
    text = re.sub(r"(\d)([ก-๙])", r"\1 \2", text)
    text = re.sub(r"([a-zA-Z])([ก-๙])", r"\1 \2", text)
    text = re.sub(r"([ก-๙])([a-zA-Z])", r"\1 \2", text)
    text = re.sub(r"(บาท|สตางค์|โมง|ทุ่ม)([ก-๙])", r"\1 \2", text)
    return _WHITESPACE_RE.sub(" ", text).strip()
