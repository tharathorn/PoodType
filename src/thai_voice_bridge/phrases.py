"""Wake/end phrase matching and stripping for hands-free mode."""

from __future__ import annotations

import re
from difflib import SequenceMatcher

_WHITESPACE_RE = re.compile(r"\s+")

# Live Faster-Whisper mishearings of 「เฮ้ พุดไทป์」 (must map to start only).
_WAKE_MISHEARING_ALIASES = (
    "โอเค พูดท้าย",
    "ภูทัย",
    "เทพุทธ",
)

# Observed Faster-Whisper mishearings of the coined brand + attention word.
_START_ALIASES = (
    "เฮ้ พุดไทป์",
    "เฮ พุดไทป์",
    "เฮ้ พุทไทป์",
    "เฮ พุทไทป์",
    "เฮ้ พุดไทย",
    "เฮ พุดไทย",
    "เฮ้ พุทไทย",
    "เฮ้ พูดท้าย",
    "เฮ พูดท้าย",
    "โอเค พุดไทป์",
    "โอเค พุทไทป์",
    "โอเค พูดไทย",
    "พูดท้าย",
    "hey poodtype",
    "hey put type",
    "ok poodtype",
    *_WAKE_MISHEARING_ALIASES,
)
_END_ALIASES = (
    "ส่งได้ พุดไทป์",
    "ส่งได้ พุทไทป์",
    "ส่งได้ พุดไทย",
    "ส่งได้ พุทไทย",
    "ส่งได้ พูดท้าย",
    "ส่งได้ พูดไทย",
    "ส่งได้ ภูทัย",
    "ส่งได้ เทพุทธ",
    "ส่งได้ พุดไทบ์",
)

_ATTENTION_TOKENS = ("เฮ้", "เฮ", "โอเค", "hey", "ok", "okay")
_END_MARKER = "ส่งได้"
_BRAND_COMPACT = (
    "พุดไทป์",
    "พุทไทป์",
    "พุดไทย",
    "พุทไทย",
    "พูดท้าย",
    "พูดไทย",
    "ภูทัย",
    "เทพุทธ",
    "พูไทป์",
    "poodtype",
    "puttype",
)


def normalize_phrase_text(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", (text or "").strip()).lower()


def _compact(text: str) -> str:
    return normalize_phrase_text(text).replace(" ", "")


def _best_window_ratio(haystack: str, needle: str) -> float:
    if not needle:
        return 0.0
    if needle in haystack:
        return 1.0
    best = 0.0
    n = len(needle)
    for size in range(max(1, n - 2), n + 3):
        if size > len(haystack):
            continue
        for start in range(0, len(haystack) - size + 1):
            chunk = haystack[start : start + size]
            best = max(best, SequenceMatcher(None, chunk, needle).ratio())
            if best >= 1.0:
                return best
    return best


def _phrase_candidates(phrase: str) -> tuple[str, ...]:
    needle = normalize_phrase_text(phrase)
    if needle.startswith(_END_MARKER) or _END_MARKER in needle:
        extras = _END_ALIASES
    else:
        extras = _START_ALIASES
    seen: list[str] = []
    for item in (phrase, *extras):
        norm = normalize_phrase_text(item)
        if norm and norm not in seen:
            seen.append(norm)
    return tuple(seen)


def _has_brand_sound(haystack: str) -> bool:
    compact = _compact(haystack)
    return any(brand in compact for brand in _BRAND_COMPACT)


def _has_attention(haystack: str) -> bool:
    tokens = normalize_phrase_text(haystack).split()
    compact = _compact(haystack)
    for token in _ATTENTION_TOKENS:
        if token in tokens or compact.startswith(token):
            return True
    return False


def _is_start_phrase(phrase: str) -> bool:
    needle = normalize_phrase_text(phrase)
    return not (needle.startswith(_END_MARKER) or _END_MARKER in needle)


def _start_alias_safe_with_end_marker(alias: str) -> bool:
    """Brand-only wake aliases must not collide with end-phrase text."""
    return _has_attention(alias)


def contains_phrase(text: str, phrase: str, *, tolerance: float = 0.8) -> bool:
    haystack = normalize_phrase_text(text)
    if not haystack:
        return False
    compact_h = _compact(haystack)
    matching_start = _is_start_phrase(phrase)
    end_marker_present = _END_MARKER in haystack
    for needle in _phrase_candidates(phrase):
        # "ส่งได้ พูดท้าย" / "ส่งได้ ภูทัย" share brand sounds with wake
        # mishearings — only attention-bearing start aliases may match.
        if (
            matching_start
            and end_marker_present
            and not _start_alias_safe_with_end_marker(needle)
        ):
            continue
        if needle in haystack or _compact(needle) in compact_h:
            return True
        tokens = [token for token in needle.split(" ") if token]
        # Fuzzy only for multi-token aliases — single tokens like "พูดท้าย"
        # otherwise false-match "ที่สุดท้าย".
        if len(tokens) < 2:
            continue
        if all(token in haystack for token in tokens):
            return True
        # Require the leading attention token so "ส่งได้ พุดไทป์" does not
        # fuzzy-match "เฮ้ พุดไทป์" via the shared brand.
        if tokens[0] not in haystack and tokens[0] not in compact_h:
            continue
        if _best_window_ratio(haystack, needle) >= tolerance:
            return True
        if _best_window_ratio(compact_h, _compact(needle)) >= tolerance:
            return True

    # Live Whisper often maps "เฮ้ พุดไทป์" → "โอเค พูดท้าย" / "ภูทัย".
    if matching_start and _has_brand_sound(haystack):
        # End phrase also contains the brand — never treat it as a start.
        if end_marker_present:
            return False
        if _has_attention(haystack):
            return True
        # Short window that is mostly the brand alone.
        if len(compact_h) <= 12:
            return True
    if (not matching_start) and end_marker_present and _has_brand_sound(haystack):
        return True
    return False


def _matched_alias_prefix(text: str, phrase: str, *, tolerance: float) -> str | None:
    haystack = normalize_phrase_text(text)
    best: str | None = None
    for needle in _phrase_candidates(phrase):
        if haystack.startswith(needle):
            if best is None or len(needle) > len(best):
                best = needle
            continue
        prefix = haystack[: max(len(needle) + 4, len(needle))]
        if SequenceMatcher(None, prefix[: len(needle)], needle).ratio() >= tolerance:
            if best is None or len(needle) > len(best):
                best = needle
    return best


def _strip_leading_phrase(text: str, phrase: str, *, tolerance: float) -> str:
    matched = _matched_alias_prefix(text, phrase, tolerance=tolerance)
    if not matched:
        return text.strip()
    parts = normalize_phrase_text(text).split()
    phrase_parts = matched.split()
    if len(parts) >= len(phrase_parts):
        # Prefer original spacing from remaining raw tokens roughly.
        raw_parts = text.split()
        if len(raw_parts) >= len(phrase_parts):
            return " ".join(raw_parts[len(phrase_parts) :]).strip()
        return " ".join(parts[len(phrase_parts) :]).strip()
    return text.strip()


def _strip_trailing_phrase(text: str, phrase: str, *, tolerance: float) -> str:
    haystack = normalize_phrase_text(text)
    best: str | None = None
    for needle in _phrase_candidates(phrase):
        if haystack.endswith(needle):
            if best is None or len(needle) > len(best):
                best = needle
            continue
        suffix = haystack[-max(len(needle) + 4, len(needle)) :]
        if SequenceMatcher(None, suffix[-len(needle) :], needle).ratio() >= tolerance:
            if best is None or len(needle) > len(best):
                best = needle
    if not best:
        return text.strip()
    phrase_parts = best.split()
    raw_parts = text.split()
    if len(raw_parts) >= len(phrase_parts):
        return " ".join(raw_parts[: -len(phrase_parts)]).strip()
    return text.strip()


def strip_command_phrases(
    text: str,
    *,
    start_phrase: str,
    end_phrase: str,
    tolerance: float = 0.8,
) -> str:
    result = _WHITESPACE_RE.sub(" ", (text or "").strip())
    if not result:
        return ""
    if contains_phrase(result, start_phrase, tolerance=tolerance):
        result = _strip_leading_phrase(result, start_phrase, tolerance=tolerance)
    if contains_phrase(result, end_phrase, tolerance=tolerance):
        result = _strip_trailing_phrase(result, end_phrase, tolerance=tolerance)
    return _WHITESPACE_RE.sub(" ", result).strip()
