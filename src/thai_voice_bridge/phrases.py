"""Wake/end phrase matching and stripping for hands-free mode.

Includes offline token-stream normalization and trailing-window helpers so
wake/end detection can run on short ASR chunks without microphone I/O.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from difflib import SequenceMatcher

_WHITESPACE_RE = re.compile(r"\s+")

# Default bounds for low-latency streaming phrase checks.
DEFAULT_STREAM_MAX_CHARS = 64
DEFAULT_STREAM_MAX_TOKENS = 12

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
    "โอเค พูดท้าย",
    "โอเค พุดไทป์",
    "โอเค พุทไทป์",
    "โอเค พูดไทย",
    "เทพุทธ",
    "ภูทัย",
    "พูดท้าย",
    "hey poodtype",
    "hey put type",
    "ok poodtype",
)
_END_ALIASES = (
    "ส่งได้ พุดไทป์",
    "ส่งได้ พุทไทป์",
    "ส่งได้ พุดไทย",
    "ส่งได้ พุทไทย",
    "ส่งได้ พูดท้าย",
    "ส่งได้ พูดไทย",
    "ส่งได้ ภูทัย",
    "ส่งได้ พุดไทบ์",
)

_ATTENTION_TOKENS = ("เฮ้", "เฮ", "โอเค", "hey", "ok", "okay")
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


def normalize_token_stream(
    *parts: str | Iterable[str] | None,
    collapse_stutter: bool = True,
) -> str:
    """Normalize and join incremental ASR chunks/tokens into one phrase string.

    Accepts strings and/or iterables of strings so callers can push either full
    Whisper window text or token lists without microphone/hardware deps.
    """
    chunks: list[str] = []
    for part in parts:
        if part is None:
            continue
        if isinstance(part, str):
            chunks.append(part)
        else:
            chunks.extend("" if item is None else str(item) for item in part)
    text = normalize_phrase_text(" ".join(chunks))
    if not text:
        return ""
    tokens = text.split(" ")
    if collapse_stutter:
        collapsed: list[str] = []
        for token in tokens:
            if not collapsed or collapsed[-1] != token:
                collapsed.append(token)
        tokens = collapsed
    return " ".join(tokens)


def tokenize_phrase(text: str) -> tuple[str, ...]:
    """Return normalized whitespace tokens (no stutter collapse)."""
    normalized = normalize_token_stream(text, collapse_stutter=False)
    if not normalized:
        return ()
    return tuple(normalized.split(" "))


def streaming_text_window(
    text: str,
    *,
    max_chars: int = DEFAULT_STREAM_MAX_CHARS,
    max_tokens: int = DEFAULT_STREAM_MAX_TOKENS,
) -> str:
    """Return a trailing normalized window for low-latency phrase matching."""
    tokens = list(tokenize_phrase(text))
    if max_tokens > 0 and len(tokens) > max_tokens:
        tokens = tokens[-max_tokens:]
    joined = " ".join(tokens)
    if max_chars > 0 and len(joined) > max_chars:
        # Prefer whole trailing tokens that fit the char budget.
        kept: list[str] = []
        total = 0
        for token in reversed(tokens):
            extra = len(token) + (1 if kept else 0)
            if total + extra > max_chars:
                break
            kept.append(token)
            total += extra
        if kept:
            joined = " ".join(reversed(kept))
        else:
            # Single oversize token: keep its tail.
            joined = joined[-max_chars:]
    return joined


class StreamingPhraseWindow:
    """Accumulate ASR chunks and match phrases against a latency-bounded tail."""

    def __init__(
        self,
        *,
        max_chars: int = DEFAULT_STREAM_MAX_CHARS,
        max_tokens: int = DEFAULT_STREAM_MAX_TOKENS,
        collapse_stutter: bool = True,
    ) -> None:
        self.max_chars = max_chars
        self.max_tokens = max_tokens
        self.collapse_stutter = collapse_stutter
        self._parts: list[str] = []

    def push(self, chunk: str) -> str:
        if chunk:
            self._parts.append(str(chunk))
        return self.window()

    def extend(self, chunks: Iterable[str]) -> str:
        for chunk in chunks:
            if chunk:
                self._parts.append(str(chunk))
        return self.window()

    def clear(self) -> None:
        self._parts.clear()

    def text(self) -> str:
        return normalize_token_stream(
            *self._parts, collapse_stutter=self.collapse_stutter
        )

    def window(self) -> str:
        return streaming_text_window(
            self.text(),
            max_chars=self.max_chars,
            max_tokens=self.max_tokens,
        )

    def contains_phrase(self, phrase: str, *, tolerance: float = 0.8) -> bool:
        return contains_phrase(self.window(), phrase, tolerance=tolerance)


def contains_phrase_low_latency(
    text: str,
    phrase: str,
    *,
    tolerance: float = 0.8,
    max_chars: int = DEFAULT_STREAM_MAX_CHARS,
    max_tokens: int = DEFAULT_STREAM_MAX_TOKENS,
) -> bool:
    """Match against a trailing stream window only (smaller fuzzy search space)."""
    return contains_phrase(
        streaming_text_window(text, max_chars=max_chars, max_tokens=max_tokens),
        phrase,
        tolerance=tolerance,
    )


def _best_window_ratio(
    haystack: str,
    needle: str,
    *,
    min_ratio: float = 0.0,
) -> float:
    """Best SequenceMatcher ratio over sliding windows, with early exit."""
    if not needle:
        return 0.0
    if needle in haystack:
        return 1.0
    best = 0.0
    n = len(needle)
    # Prefer scanning near the end first — wake/end phrases usually sit in the
    # newest ASR tail, so early exit cuts match latency on long transcripts.
    for size in range(max(1, n - 2), n + 3):
        if size > len(haystack):
            continue
        limit = len(haystack) - size
        for start in range(limit, -1, -1):
            chunk = haystack[start : start + size]
            ratio = SequenceMatcher(None, chunk, needle).ratio()
            if ratio > best:
                best = ratio
                if best >= 1.0 or (min_ratio > 0.0 and best >= min_ratio):
                    return best
    return best


def _phrase_candidates(phrase: str) -> tuple[str, ...]:
    needle = normalize_phrase_text(phrase)
    if needle.startswith("ส่งได้") or "ส่งได้" in needle:
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
    return not (needle.startswith("ส่งได้") or "ส่งได้" in needle)


def contains_phrase(text: str, phrase: str, *, tolerance: float = 0.8) -> bool:
    haystack = normalize_phrase_text(text)
    if not haystack:
        return False
    compact_h = _compact(haystack)
    for needle in _phrase_candidates(phrase):
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
        if _best_window_ratio(haystack, needle, min_ratio=tolerance) >= tolerance:
            return True
        if (
            _best_window_ratio(compact_h, _compact(needle), min_ratio=tolerance)
            >= tolerance
        ):
            return True

    # Live Whisper often maps "เฮ้ พุดไทป์" → "โอเค พูดท้าย" / "ภูทัย".
    if _is_start_phrase(phrase) and _has_brand_sound(haystack):
        # End phrase also contains the brand — never treat it as a start.
        if "ส่งได้" in haystack:
            return False
        if _has_attention(haystack):
            return True
        # Short window that is mostly the brand alone.
        if len(compact_h) <= 12:
            return True
    if (not _is_start_phrase(phrase)) and ("ส่งได้" in haystack) and _has_brand_sound(
        haystack
    ):
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
