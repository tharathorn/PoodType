"""Unicode script-sanity gate for Thai-mode transcripts.

Fail closed on unexpected scripts (e.g. Bengali mixed into Thai). Never strip
or rewrite potentially meaningful text — reject the whole paste instead.
"""

from __future__ import annotations

import sys
import unicodedata
from collections.abc import Iterable

# ASCII + common editor punctuation used in Thai/English technical dictation.
DEFAULT_ALLOWED_PUNCTUATION = frozenset(
    ".,!?;:'\"()-[]{}/@#$%&*+=<>~`|_\\^"
    "…—–“”‘’«»·•°±×÷"
    "฿€£¥₩"
)

# Concise user-facing retry copy (no transcript rewrite; nothing was pasted).
SCRIPT_SANITY_RETRY_PROMPT = (
    "Unexpected script in transcript (e.g. Bengali). "
    "Nothing was pasted — please retry dictation."
)

# Named ranges used only for error labeling (not as allowlists).
_SCRIPT_LABELS: tuple[tuple[int, int, str], ...] = (
    (0x0900, 0x097F, "Devanagari"),
    (0x0980, 0x09FF, "Bengali"),
    (0x0A00, 0x0A7F, "Gurmukhi"),
    (0x0A80, 0x0AFF, "Gujarati"),
    (0x0B00, 0x0B7F, "Oriya"),
    (0x0B80, 0x0BFF, "Tamil"),
    (0x0C00, 0x0C7F, "Telugu"),
    (0x0C80, 0x0CFF, "Kannada"),
    (0x0D00, 0x0D7F, "Malayalam"),
    (0x0600, 0x06FF, "Arabic"),
    (0x0750, 0x077F, "Arabic"),
    (0x0400, 0x04FF, "Cyrillic"),
    (0x0500, 0x052F, "Cyrillic"),
    (0x0370, 0x03FF, "Greek"),
    (0x0590, 0x05FF, "Hebrew"),
    (0x3040, 0x309F, "Hiragana"),
    (0x30A0, 0x30FF, "Katakana"),
    (0x4E00, 0x9FFF, "Han"),
    (0xAC00, 0xD7AF, "Hangul"),
    (0x1100, 0x11FF, "Hangul"),
)


class ScriptSanityError(ValueError):
    """Thai-mode transcript contains unexpected Unicode scripts."""

    def __init__(self, message: str, *, scripts: tuple[str, ...] = ()) -> None:
        super().__init__(message)
        self.scripts = scripts
        self.retry_prompt = SCRIPT_SANITY_RETRY_PROMPT


def _label_script(codepoint: int) -> str:
    for start, end, name in _SCRIPT_LABELS:
        if start <= codepoint <= end:
            return name
    return f"U+{codepoint:04X}"


def _is_latin_letter(ch: str) -> bool:
    code = ord(ch)
    if ("A" <= ch <= "Z") or ("a" <= ch <= "z"):
        return True
    # Latin-1 Supplement through Latin Extended-B (names / loanwords).
    if 0x00C0 <= code <= 0x024F:
        return unicodedata.category(ch).startswith("L")
    return False


def _is_thai(ch: str) -> bool:
    return 0x0E00 <= ord(ch) <= 0x0E7F


def _is_ascii_digit(ch: str) -> bool:
    return "0" <= ch <= "9"


# Minimal Cc allowlist used by ordinary multiline transcripts (also via isspace).
_ALLOWED_CONTROLS = frozenset("\t\n\r")


def _is_allowed_char(ch: str, punctuation: frozenset[str]) -> bool:
    # Explicit whitespace allowlist: Zs/Zl/Zp via isspace, plus tab/LF/CR.
    if ch in _ALLOWED_CONTROLS or (ch.isspace() and unicodedata.category(ch)[0] == "Z"):
        return True
    if _is_ascii_digit(ch) or _is_thai(ch) or _is_latin_letter(ch):
        return True
    if ch in punctuation:
        return True
    code = ord(ch)
    # Combining marks that attach to allowed bases (Latin/Thai diacritics).
    if unicodedata.category(ch) in {"Mn", "Mc", "Me"} and (
        0x0300 <= code <= 0x036F or _is_thai(ch)
    ):
        return True
    return False


def unexpected_scripts(
    text: str,
    *,
    allowed_punctuation: Iterable[str] | None = None,
) -> tuple[str, ...]:
    """Return sorted unique unexpected script labels found in text."""
    punct = (
        frozenset(allowed_punctuation)
        if allowed_punctuation is not None
        else DEFAULT_ALLOWED_PUNCTUATION
    )
    found: set[str] = set()
    for ch in text or "":
        if _is_allowed_char(ch, punct):
            continue
        category = unicodedata.category(ch)
        if category in {"Cc", "Cf"}:
            found.add(f"Control/{category}")
            continue
        found.add(_label_script(ord(ch)))
    return tuple(sorted(found))


def check_thai_mode_script(
    text: str,
    *,
    allowed_punctuation: Iterable[str] | None = None,
) -> None:
    """Raise ScriptSanityError when Thai-mode text contains unexpected scripts."""
    scripts = unexpected_scripts(text, allowed_punctuation=allowed_punctuation)
    if not scripts:
        return
    joined = ", ".join(scripts)
    raise ScriptSanityError(
        f"Unexpected script(s) in Thai-mode transcript: {joined}",
        scripts=scripts,
    )


def show_script_sanity_retry_prompt(message: str | None = None) -> None:
    """Show a concise retry prompt (MessageBox on Windows; no-op elsewhere)."""
    text = (message or SCRIPT_SANITY_RETRY_PROMPT).strip()
    if not text or sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(  # type: ignore[attr-defined]
            0,
            text,
            "PoodType",
            0x00000030,  # MB_ICONWARNING
        )
    except Exception:  # noqa: BLE001 — UI prompt must never break the pipeline
        pass
