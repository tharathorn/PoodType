"""Wake/end phrase matching and stripping for hands-free mode."""

from __future__ import annotations

import re
from difflib import SequenceMatcher

_WHITESPACE_RE = re.compile(r"\s+")


def normalize_phrase_text(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", (text or "").strip()).lower()


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


def contains_phrase(text: str, phrase: str, *, tolerance: float = 0.8) -> bool:
    haystack = normalize_phrase_text(text)
    needle = normalize_phrase_text(phrase)
    if not haystack or not needle:
        return False
    if needle in haystack:
        return True
    tokens = [token for token in needle.split(" ") if token]
    if len(tokens) >= 2 and not all(token in haystack for token in tokens):
        return False
    return _best_window_ratio(haystack, needle) >= tolerance


def _strip_leading_phrase(text: str, phrase: str, *, tolerance: float) -> str:
    haystack = normalize_phrase_text(text)
    needle = normalize_phrase_text(phrase)
    if not needle:
        return text.strip()
    if haystack.startswith(needle):
        parts = text.split()
        phrase_parts = phrase.split()
        if len(parts) >= len(phrase_parts):
            return " ".join(parts[len(phrase_parts) :]).strip()
    # Fuzzy: only strip when the whole text nearly starts with the phrase window
    prefix = haystack[: max(len(needle) + 4, len(needle))]
    if SequenceMatcher(None, prefix[: len(needle)], needle).ratio() >= tolerance:
        parts = text.split()
        phrase_parts = phrase.split()
        if len(parts) >= len(phrase_parts):
            return " ".join(parts[len(phrase_parts) :]).strip()
    return text.strip()


def _strip_trailing_phrase(text: str, phrase: str, *, tolerance: float) -> str:
    haystack = normalize_phrase_text(text)
    needle = normalize_phrase_text(phrase)
    if not needle:
        return text.strip()
    if haystack.endswith(needle):
        parts = text.split()
        phrase_parts = phrase.split()
        if len(parts) >= len(phrase_parts):
            return " ".join(parts[: -len(phrase_parts)]).strip()
    suffix = haystack[-max(len(needle) + 4, len(needle)) :]
    if SequenceMatcher(None, suffix[-len(needle) :], needle).ratio() >= tolerance:
        parts = text.split()
        phrase_parts = phrase.split()
        if len(parts) >= len(phrase_parts):
            return " ".join(parts[: -len(phrase_parts)]).strip()
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
        # Strip start only when it appears at the beginning of the utterance.
        if normalize_phrase_text(result).startswith(
            normalize_phrase_text(start_phrase)
        ) or SequenceMatcher(
            None,
            normalize_phrase_text(result)[: len(normalize_phrase_text(start_phrase))],
            normalize_phrase_text(start_phrase),
        ).ratio() >= tolerance:
            result = _strip_leading_phrase(result, start_phrase, tolerance=tolerance)
    if contains_phrase(result, end_phrase, tolerance=tolerance):
        if normalize_phrase_text(result).endswith(
            normalize_phrase_text(end_phrase)
        ) or SequenceMatcher(
            None,
            normalize_phrase_text(result)[-len(normalize_phrase_text(end_phrase)) :],
            normalize_phrase_text(end_phrase),
        ).ratio() >= tolerance:
            result = _strip_trailing_phrase(result, end_phrase, tolerance=tolerance)
    return _WHITESPACE_RE.sub(" ", result).strip()
