"""Offline Thai text normalizer and punctuation sanitizer for speech synthesis.

Prepares written Thai (and mixed Thai/Latin) text for TTS engines entirely
offline — no network, audio hardware, or external tokenizers.

Pipeline (see ``preprocess_for_synthesis``):

1. Unicode NFC + strip control / zero-width characters
2. Optionally expand emails / URLs / paths via ``speak_paths`` (while structural
   punctuation is still intact)
3. Sanitize punctuation (smart quotes, dashes, repeats, markdown noise)
4. Optionally expand Arabic digits into Thai spoken numerals
5. Collapse whitespace
"""

from __future__ import annotations

import re
import unicodedata

from thai_voice_bridge.speak_paths import speak_paths

# --- Digit / unit tables (Arabic → Thai spoken) --------------------------------

_DIGIT_WORDS: tuple[str, ...] = (
    "ศูนย์",
    "หนึ่ง",
    "สอง",
    "สาม",
    "สี่",
    "ห้า",
    "หก",
    "เจ็ด",
    "แปด",
    "เก้า",
)

# Units below one million, largest first.
_SCALE_UNITS: tuple[tuple[int, str], ...] = (
    (100_000, "แสน"),
    (10_000, "หมื่น"),
    (1_000, "พัน"),
    (100, "ร้อย"),
    (10, "สิบ"),
)

# Long digit runs (phones, IDs) are read digit-by-digit for clarity.
_DIGIT_BY_DIGIT_MIN_LEN = 7

_NUMBER_RE = re.compile(
    r"(?<![A-Za-z0-9_])"
    r"(?P<sign>-)?"
    r"(?P<int>\d{1,15})"
    r"(?:(?P<sep>[.,])(?P<frac>\d{1,6}))?"
    r"(?![A-Za-z0-9_])"
)

_WHITESPACE_RE = re.compile(r"\s+")
_CONTROL_RE = re.compile(
    r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f"
    r"\u200b-\u200f\u202a-\u202e\u2060\ufeff]"
)
_HTML_TAG_RE = re.compile(r"</?[a-zA-Z][^>]*>")
_MARKDOWN_EMPHASIS_RE = re.compile(r"[*_`~]{1,3}")
_REPEATED_BANG_RE = re.compile(r"!{2,}")
_REPEATED_QUESTION_RE = re.compile(r"\?{2,}")
_REPEATED_DOT_RE = re.compile(r"\.{3,}|…+")
_REPEATED_DASH_RE = re.compile(r"-{2,}|—+|–+")
_SPACE_BEFORE_PUNCT_RE = re.compile(r"\s+([,.;:!?%)])")
_SPACE_AFTER_OPEN_RE = re.compile(r"([(])\s+")
_MULTI_IDENTICAL_PUNCT_RE = re.compile(r"([,.;:!?])\1+")

# Typographic / fullwidth punctuation → TTS-friendly forms.
# Structural email/URL marks (@ . / :) are left alone so callers can run
# speak_paths before this pass; symbols that TTS would mis-read are expanded.
_PUNCT_TRANSLATE = str.maketrans(
    {
        "“": '"',
        "”": '"',
        "„": '"',
        "«": '"',
        "»": '"',
        "‘": "'",
        "’": "'",
        "‚": "'",
        "′": "'",
        "″": '"',
        "–": ",",
        "—": ",",
        "−": "-",
        "‐": "-",
        "‑": "-",
        "・": " ",
        "·": " ",
        "•": " ",
        "‧": " ",
        "ฯ": ",",
        "【": " ",
        "】": " ",
        "「": " ",
        "」": " ",
        "『": " ",
        "』": " ",
        "（": "(",
        "）": ")",
        "［": " ",
        "］": " ",
        "｛": " ",
        "｝": " ",
        "：": ":",
        "；": ";",
        "，": ",",
        "．": ".",
        "！": "!",
        "？": "?",
        "／": "/",
        "％": "%",
        "＃": " ",
        "＊": " ",
        "＿": " ",
        "～": " ",
        "｜": " ",
        "|": " ",
        "^": " ",
        "{": " ",
        "}": " ",
        "[": " ",
        "]": " ",
        "<": " ",
        ">": " ",
        "=": " ",
        "#": " ",
        "*": " ",
        "_": " ",
        "`": " ",
        "~": " ",
        "\\": " ",
    }
)

_SYMBOL_EXPANSIONS: tuple[tuple[str, str], ...] = (
    ("%", " เปอร์เซ็นต์"),
    ("&", " และ "),
    ("+", " บวก "),
)


def normalize_whitespace(text: str | None) -> str:
    """Collapse runs of whitespace and strip ends."""
    return _WHITESPACE_RE.sub(" ", (text or "").strip())


def strip_controls(text: str | None) -> str:
    """NFC-normalize and remove control / zero-width characters.

    NFC (not NFKC) is used so Thai sara-am / tone clusters stay composed —
    NFKC would split สำ into base + combining marks and confuse TTS.
    Fullwidth ASCII (ＵＲＬ-style) is folded to halfwidth without NFKC.
    """
    raw = text or ""
    if not raw:
        return ""
    cleaned = unicodedata.normalize("NFC", raw)
    cleaned = _CONTROL_RE.sub("", cleaned)
    return _fold_fullwidth_ascii(cleaned)


def _fold_fullwidth_ascii(text: str) -> str:
    """Map fullwidth ASCII (!–~) to halfwidth without touching Thai letters."""
    out: list[str] = []
    for ch in text:
        code = ord(ch)
        if 0xFF01 <= code <= 0xFF5E:
            out.append(chr(code - 0xFEE0))
        elif code == 0x3000:  # ideographic space
            out.append(" ")
        else:
            out.append(ch)
    return "".join(out)


def sanitize_punctuation(text: str | None) -> str:
    """Normalize punctuation so TTS engines do not spell out decorative marks.

    - NFC-normalize and drop control / zero-width characters
    - Strip light HTML tags and markdown emphasis markers
    - Map smart quotes, dashes, ellipses, and fullwidth punct to plain forms
    - Expand ``%``, ``&``, ``+`` into Thai spoken words
    - Collapse repeated ``!``, ``?``, ``...``, and dash runs into a single pause
    - Tighten spaces around common sentence punctuation
    """
    cleaned = strip_controls(text)
    if not cleaned:
        return ""

    cleaned = _HTML_TAG_RE.sub(" ", cleaned)
    cleaned = _MARKDOWN_EMPHASIS_RE.sub("", cleaned)
    cleaned = cleaned.translate(_PUNCT_TRANSLATE)

    for src, dst in _SYMBOL_EXPANSIONS:
        cleaned = cleaned.replace(src, dst)

    cleaned = _REPEATED_DOT_RE.sub(",", cleaned)
    cleaned = _REPEATED_DASH_RE.sub(",", cleaned)
    cleaned = _REPEATED_BANG_RE.sub("!", cleaned)
    cleaned = _REPEATED_QUESTION_RE.sub("?", cleaned)
    cleaned = _MULTI_IDENTICAL_PUNCT_RE.sub(r"\1", cleaned)

    cleaned = _SPACE_BEFORE_PUNCT_RE.sub(r"\1", cleaned)
    cleaned = _SPACE_AFTER_OPEN_RE.sub(r"\1", cleaned)
    # Drop leftover straight quotes — TTS often spells them as "quote".
    cleaned = cleaned.replace('"', " ").replace("'", " ")
    return normalize_whitespace(cleaned)


def arabic_to_thai_spoken(value: int) -> str:
    """Convert an integer to Thai spoken numerals (supports negatives)."""
    if value == 0:
        return _DIGIT_WORDS[0]
    if value < 0:
        return "ลบ" + arabic_to_thai_spoken(-value)
    if value >= 1_000_000_000_000:  # defensive: read digit-by-digit
        return "".join(_DIGIT_WORDS[int(ch)] for ch in str(value) if ch.isdigit())

    parts: list[str] = []
    millions = value // 1_000_000
    rest = value % 1_000_000
    if millions:
        parts.append(arabic_to_thai_spoken(millions) + "ล้าน")
    if rest:
        parts.append(_speak_under_million(rest))
    return "".join(parts)


def _speak_under_million(n: int) -> str:
    """Read 1 ≤ n < 1_000_000 using Thai place-value rules."""
    if n <= 0 or n >= 1_000_000:
        raise ValueError("n must be in 1..999999")

    parts: list[str] = []
    remaining = n

    for unit_value, unit_word in _SCALE_UNITS:
        coeff = remaining // unit_value
        if coeff == 0:
            continue
        remaining %= unit_value

        if unit_value == 10:
            if coeff == 1:
                parts.append("สิบ")
            elif coeff == 2:
                parts.append("ยี่สิบ")
            else:
                parts.append(_DIGIT_WORDS[coeff] + "สิบ")
            continue

        if coeff == 1:
            parts.append("หนึ่ง" + unit_word)
        else:
            parts.append(_DIGIT_WORDS[coeff] + unit_word)

    if remaining:
        # Units place: เอ็ด after a tens/higher place, else หนึ่ง.
        if remaining == 1 and parts:
            parts.append("เอ็ด")
        else:
            parts.append(_DIGIT_WORDS[remaining])

    return "".join(parts)


def _speak_digit_run(digits: str) -> str:
    return " ".join(_DIGIT_WORDS[int(ch)] for ch in digits)


def _speak_number_match(match: re.Match[str]) -> str:
    sign = match.group("sign")
    integer = match.group("int")
    frac = match.group("frac")

    # Long runs → digit-by-digit (phones / IDs).
    if frac is None and len(integer) >= _DIGIT_BY_DIGIT_MIN_LEN:
        spoken = _speak_digit_run(integer)
        return f"ลบ {spoken}" if sign else spoken

    spoken_int = arabic_to_thai_spoken(int(integer))
    if sign:
        spoken_int = "ลบ" + spoken_int

    if frac is None:
        return spoken_int

    # Decimal fractional digits are always read individually after จุด.
    frac_spoken = "".join(_DIGIT_WORDS[int(ch)] for ch in frac)
    return f"{spoken_int}จุด{frac_spoken}"


def expand_digits_for_speech(text: str | None) -> str:
    """Replace Arabic number spans with Thai spoken forms for TTS."""
    raw = text or ""
    if not raw:
        return ""
    return _NUMBER_RE.sub(_speak_number_match, raw)


def preprocess_for_synthesis(
    text: str | None,
    *,
    expand_digits: bool = True,
    expand_paths: bool = True,
) -> str:
    """Full offline TTS preprocessing pipeline.

    Parameters
    ----------
    text:
        Source text (Thai, Latin, or mixed). ``None`` / blank → ``\"\"``.
    expand_digits:
        When True, convert Arabic numerals to Thai spoken words.
    expand_paths:
        When True, expand emails, URLs, and filesystem paths via ``speak_paths``.
    """
    if text is None:
        return ""

    # Keep structural punctuation intact for path/email expansion first.
    cleaned = strip_controls(text)
    cleaned = normalize_whitespace(cleaned)
    if not cleaned:
        return ""

    if expand_paths:
        cleaned = speak_paths(cleaned)

    cleaned = sanitize_punctuation(cleaned)
    if not cleaned:
        return ""

    if expand_digits:
        cleaned = expand_digits_for_speech(cleaned)

    return normalize_whitespace(cleaned)


# Aliases matching the naming used by sibling normalizers.
normalize_for_tts = preprocess_for_synthesis
sanitize_for_speech = sanitize_punctuation
normalize_thai_for_speech = preprocess_for_synthesis

__all__ = [
    "arabic_to_thai_spoken",
    "expand_digits_for_speech",
    "normalize_for_tts",
    "normalize_thai_for_speech",
    "normalize_whitespace",
    "preprocess_for_synthesis",
    "sanitize_for_speech",
    "sanitize_punctuation",
    "strip_controls",
]
