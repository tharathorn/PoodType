"""Offline Thai spoken-number, currency, punctuation, and ASR stutter normalization."""

from __future__ import annotations

import re

# Digit / unit words (longest-first for greedy matching).
_NUMBER_WORDS: tuple[tuple[str, int, str], ...] = (
    ("หนึ่ง", 1, "digit"),
    ("เอ็ด", 1, "digit"),
    ("สอง", 2, "digit"),
    ("ยี่", 2, "digit"),
    ("สาม", 3, "digit"),
    ("สี่", 4, "digit"),
    ("ห้า", 5, "digit"),
    ("หก", 6, "digit"),
    ("เจ็ด", 7, "digit"),
    ("แปด", 8, "digit"),
    ("เก้า", 9, "digit"),
    ("ศูนย์", 0, "digit"),
    ("ล้าน", 1_000_000, "unit"),
    ("แสน", 100_000, "unit"),
    ("หมื่น", 10_000, "unit"),
    ("พัน", 1_000, "unit"),
    ("ร้อย", 100, "unit"),
    ("สิบ", 10, "unit"),
)

_NUMBER_WORDS_BY_LEN = tuple(sorted(_NUMBER_WORDS, key=lambda item: len(item[0]), reverse=True))
_NUMBER_LITERALS = tuple(word for word, _, _ in _NUMBER_WORDS_BY_LEN)
_NUMBER_TOKEN_RE = "|".join(re.escape(w) for w in _NUMBER_LITERALS)
_SPOKEN_NUMBER_RE = re.compile(rf"(?:{_NUMBER_TOKEN_RE})(?:\s*(?:{_NUMBER_TOKEN_RE}))*", re.UNICODE)

_CURRENCY_RE = re.compile(
    rf"(?P<baht>{_SPOKEN_NUMBER_RE.pattern}|\d+)\s*บาท"
    rf"(?:\s*(?P<satang_after>{_SPOKEN_NUMBER_RE.pattern}|\d+)\s*สตางค์)?"
    rf"|(?P<satang_only>{_SPOKEN_NUMBER_RE.pattern}|\d+)\s*สตางค์",
    re.UNICODE,
)

# Spoken punctuation → symbol. Longer phrases first.
_PUNCTUATION_MAP: tuple[tuple[str, str], ...] = (
    ("เครื่องหมายคำถาม", "?"),
    ("เปิดวงเล็บ", "("),
    ("ปิดวงเล็บ", ")"),
    ("เปอร์เซ็นต์", "%"),
    ("อัศเจรีย์", "!"),
    ("มหัพภาค", "."),
    ("จุลภาค", ","),
    ("อัฒภาค", ";"),
    ("สองจุด", ":"),
    ("โคลอน", ":"),
    ("คอมมา", ","),
    ("เซมิโคลอน", ";"),
    ("ขีดกลาง", "-"),
    ("แดช", "-"),
    ("จุด", "."),
    ("ทับ", "/"),
    ("ขีด", "-"),
)

_PUNCT_RE = re.compile(
    "|".join(re.escape(src) for src, _ in sorted(_PUNCTUATION_MAP, key=lambda p: len(p[0]), reverse=True)),
    re.UNICODE,
)
_PUNCT_LOOKUP = dict(_PUNCTUATION_MAP)

_WHITESPACE_RE = re.compile(r"\s+")
_SPACE_BEFORE_PUNCT_RE = re.compile(r"\s+([.,:;?!%/)])")
_SPACE_AFTER_OPEN_RE = re.compile(r"([(])\s+")
_SPACE_AROUND_SLASH_DASH_RE = re.compile(r"\s*([/\-])\s*")


def _collapse_ws(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", (text or "").strip())


def remove_stutter_tokens(text: str) -> str:
    """Collapse consecutive identical whitespace-separated ASR tokens."""
    cleaned = _collapse_ws(text)
    if not cleaned:
        return ""
    parts = cleaned.split(" ")
    out: list[str] = []
    for token in parts:
        if out and out[-1] == token:
            continue
        out.append(token)
    return " ".join(out)


def _tokenize_number_words(chunk: str) -> list[tuple[str, int, str]] | None:
    compact = chunk.replace(" ", "")
    if not compact:
        return None
    tokens: list[tuple[str, int, str]] = []
    i = 0
    while i < len(compact):
        matched = False
        for word, value, kind in _NUMBER_WORDS_BY_LEN:
            if compact.startswith(word, i):
                tokens.append((word, value, kind))
                i += len(word)
                matched = True
                break
        if not matched:
            return None
    return tokens or None


def spoken_number_to_int(chunk: str) -> int | None:
    """Convert a Thai spoken-number phrase to an integer, or None if invalid."""
    stripped = (chunk or "").strip()
    if not stripped:
        return None
    if stripped.isdigit():
        return int(stripped)
    tokens = _tokenize_number_words(stripped)
    if tokens is None:
        return None

    total = 0
    current = 0
    for _word, value, kind in tokens:
        if kind == "digit":
            current = value
            continue
        # unit
        if value == 10:
            total += (current if current else 1) * 10
            current = 0
        else:
            total += (current if current else 1) * value
            current = 0
    total += current
    return total


def normalize_spoken_numbers(text: str) -> str:
    """Replace Thai spoken-number spans with Arabic digits (offline)."""

    def _replace(match: re.Match[str]) -> str:
        value = spoken_number_to_int(match.group(0))
        if value is None:
            return match.group(0)
        return str(value)

    return _SPOKEN_NUMBER_RE.sub(_replace, text or "")


def _format_baht(baht: int, satang: int | None = None) -> str:
    if satang is None:
        return f"{baht} บาท"
    if baht == 0 and satang is not None:
        return f"0.{satang:02d} บาท"
    return f"{baht}.{satang:02d} บาท"


def normalize_currency(text: str) -> str:
    """Normalize spoken/digit amounts with บาท / สตางค์ into compact baht form."""

    def _replace(match: re.Match[str]) -> str:
        if match.group("satang_only") is not None:
            satang = spoken_number_to_int(match.group("satang_only"))
            if satang is None:
                return match.group(0)
            return _format_baht(0, satang)

        baht_raw = match.group("baht")
        baht = spoken_number_to_int(baht_raw) if baht_raw is not None else None
        if baht is None:
            return match.group(0)
        satang_raw = match.group("satang_after")
        if satang_raw is None:
            return _format_baht(baht)
        satang = spoken_number_to_int(satang_raw)
        if satang is None:
            return match.group(0)
        return _format_baht(baht, satang)

    return _CURRENCY_RE.sub(_replace, text or "")


def normalize_spoken_punctuation(text: str) -> str:
    """Map common Thai spoken punctuation tokens to ASCII/Thai symbols."""

    def _replace(match: re.Match[str]) -> str:
        return _PUNCT_LOOKUP.get(match.group(0), match.group(0))

    out = _PUNCT_RE.sub(_replace, text or "")
    out = _SPACE_BEFORE_PUNCT_RE.sub(r"\1", out)
    out = _SPACE_AFTER_OPEN_RE.sub(r"\1", out)
    out = _SPACE_AROUND_SLASH_DASH_RE.sub(r"\1", out)
    return _collapse_ws(out)


def normalize_text(text: str) -> str:
    """Full offline pipeline: stutter → currency → numbers → punctuation."""
    cleaned = _collapse_ws(text)
    if not cleaned:
        return ""
    cleaned = remove_stutter_tokens(cleaned)
    cleaned = normalize_currency(cleaned)
    cleaned = normalize_spoken_numbers(cleaned)
    cleaned = normalize_spoken_punctuation(cleaned)
    return cleaned
