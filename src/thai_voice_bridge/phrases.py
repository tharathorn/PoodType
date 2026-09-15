"""Offline Thai technical vocabulary and terminal-command phonetic matcher.

Maps spoken Thai / ASR soundalikes to canonical CLI tokens and product names
without network, microphone, or model calls.
"""

from __future__ import annotations

import re

_WHITESPACE_RE = re.compile(r"\s+")
# Split glued ASR spans on Latin punctuation while keeping path separators on
# already-separated tokens (handled after whitespace split).
_PUNCT_SPLIT_RE = re.compile(r"[,\.!?;…]+")
_SLASH_SPLIT_RE = re.compile(r"[/\\|]+")
_EDGE_PUNCT_RE = re.compile(r"^[\s\"'`“”‘’({\[]+|[\s\"'`“”‘’)}\],.!?;:…]+$")

# Spoken pronunciation → canonical CLI / product token (lowercase keys).
PRONUNCIATION_ALIASES: dict[str, str] = {
    # VCS / package managers / runtimes
    "กิต": "git",
    "git": "git",
    "ด็อกเกอร์": "docker",
    "ดอคเกอร์": "docker",
    "docker": "docker",
    "เอ็นพีเอ็ม": "npm",
    "เอ็นพีม": "npm",
    "npm": "npm",
    "ไพธอน": "python",
    "ไพทอน": "python",
    "python": "python",
    "ซีดี": "cd",
    "cd": "cd",
    "คอนฟิก": "config",
    "config": "config",
    "พาวเวอร์เชลล์": "PowerShell",
    "powershell": "PowerShell",
    "กิทฮับ": "GitHub",
    "กิตฮับ": "GitHub",
    "github": "GitHub",
    # Verbs / subcommands
    "พุช": "push",
    "push": "push",
    "พูล": "pull",
    "pull": "pull",
    "คอมมิท": "commit",
    "คอมมิต": "commit",
    "commit": "commit",
    "สเตตัส": "status",
    "status": "status",
    "แอด": "add",
    "add": "add",
    "ล็อก": "log",
    "log": "log",
    "รัน": "run",
    "run": "run",
    "บิลด์": "build",
    "build": "build",
    "เคลียร์": "clear",
    "clear": "clear",
    "สกรีน": "screen",
    "screen": "screen",
    "เดฟ": "dev",
    "dev": "dev",
    "อินสตอล": "install",
    "install": "install",
    "เทส": "test",
    "เทสต์": "test",
    "test": "test",
    # Flags (single letters spoken in Thai)
    "เอ็ม": "m",
    "เอ": "a",
    "พี": "p",
    "ออล": "all",
    "all": "all",
    # Product / tech vocabulary (display casing preserved)
    "โคเด็ก": "Codex",
    "โคเดกซ์": "Codex",
    "โครเด็ก": "Codex",
    "โค้ดเด็ก": "Codex",
    "codex": "Codex",
    "เคอร์เซอร์": "Cursor",
    "เคอเซอร์": "Cursor",
    "cursor": "Cursor",
    "คอมโพส": "Composer",
    "คอมโพเซอร์": "Composer",
    "composer": "Composer",
    "เอพีไอ": "API",
    "api": "API",
    "เอ็มซีพี": "MCP",
    "mcp": "MCP",
    "วินโดวส์": "Windows",
    "วินโดว์": "Windows",
    "วินโด": "Windows",
    "windows": "Windows",
}

# Multi-token spoken phrases → single output token/phrase (longest match first).
_PHRASE_ALIASES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("เคลียร์", "สกรีน"), "clear"),
    (("clear", "screen"), "clear"),
    (("ขีด", "ขีด"), "--"),
    (("ขีด",), "-"),
    (("โค้ด", "โค้ช"), "Code Coach"),
    (("โคด", "โค้ช"), "Code Coach"),
    (("code", "coach"), "Code Coach"),
    (("เดฟ", "ออเคสเตรเตอร์"), "Dev Orchestrator"),
    (("dev", "orchestrator"), "Dev Orchestrator"),
    (("ฟูล", "คอนเทนต์"), "Full Content"),
    (("full", "content"), "Full Content"),
    (("ไฮเปอร์", "เฟรม"), "HyperFrames"),
)

_PHRASE_ALIASES_SORTED: tuple[tuple[tuple[str, ...], str], ...] = tuple(
    sorted(_PHRASE_ALIASES, key=lambda item: len(item[0]), reverse=True)
)

# Display casing for free-transcript vocabulary (CLI matcher keeps lowercase).
_TECH_DISPLAY: dict[str, str] = {
    "python": "Python",
    "powershell": "PowerShell",
    "github": "GitHub",
}


def normalize_pronunciation(text: str | None) -> str:
    """Collapse whitespace, lowercase Latin letters, strip outer punctuation."""
    if text is None:
        return ""
    cleaned = _WHITESPACE_RE.sub(" ", str(text).strip())
    if not cleaned:
        return ""
    # Lowercase ASCII only — Thai casing is irrelevant.
    lowered = "".join(ch.lower() if "A" <= ch <= "Z" else ch for ch in cleaned)
    # Treat commas as soft separators; keep hyphens inside tokens (run-dev).
    lowered = lowered.replace(",", " ")
    lowered = _EDGE_PUNCT_RE.sub("", lowered)
    # Strip a trailing sentence period that is not part of a path/extension.
    if lowered.endswith(".") and not re.search(r"\.[a-z0-9]{1,5}$", lowered):
        lowered = lowered[:-1]
    return _WHITESPACE_RE.sub(" ", lowered).strip()


def tokenize_spoken(text: str | None) -> tuple[str, ...]:
    """Split spoken/ASR text into normalized pronunciation tokens."""
    normalized = normalize_pronunciation(text)
    if not normalized:
        return ()
    # Split on whitespace first so path tokens like `/var/log` stay intact.
    rough = [p for p in _WHITESPACE_RE.split(normalized) if p]
    parts: list[str] = []
    for piece in rough:
        if piece.startswith(("/", "\\", ".", "~")) or re.match(
            r"^[A-Za-z]:[\\/]", piece
        ):
            parts.append(piece)
            continue
        spaced = _PUNCT_SPLIT_RE.sub(" ", piece)
        spaced = spaced.replace("…", " ")
        # Only split slashes when the piece looks like glued CLI words.
        if "/" in spaced or "\\" in spaced or "|" in spaced:
            spaced = _SLASH_SPLIT_RE.sub(" ", spaced)
        parts.extend(p for p in _WHITESPACE_RE.split(spaced.strip()) if p)
    return tuple(parts)


def canonicalize_token(token: str | None) -> str:
    """Map one spoken token through pronunciation aliases; else return as-is."""
    raw = normalize_pronunciation(token)
    if not raw:
        return ""
    if raw in PRONUNCIATION_ALIASES:
        return PRONUNCIATION_ALIASES[raw]
    # Also try without residual inner punctuation.
    compact = raw.strip("-_")
    if compact in PRONUNCIATION_ALIASES:
        return PRONUNCIATION_ALIASES[compact]
    return raw


def _consume_phrase(
    tokens: list[str], index: int
) -> tuple[str, int] | None:
    """Longest-match multi-token phrase starting at index, if any."""
    for spoken, replacement in _PHRASE_ALIASES_SORTED:
        length = len(spoken)
        window = tokens[index : index + length]
        if len(window) != length:
            continue
        if tuple(window) == spoken:
            return replacement, index + length
    return None


def _rewrite_tokens(tokens: tuple[str, ...]) -> list[str]:
    """Apply phrase aliases, flag merges, and per-token canonicalization."""
    raw = list(tokens)
    out: list[str] = []
    i = 0
    while i < len(raw):
        phrase = _consume_phrase(raw, i)
        if phrase is not None:
            replacement, next_i = phrase
            # Flag prefixes: merge following letter/word into -x / --word.
            if replacement in {"-", "--"} and next_i < len(raw):
                flag_body = canonicalize_token(raw[next_i])
                out.append(f"{replacement}{flag_body}")
                i = next_i + 1
                continue
            out.append(replacement)
            i = next_i
            continue
        out.append(canonicalize_token(raw[i]))
        i += 1
    return out


def match_terminal_command(spoken: str | None) -> str:
    """Map a spoken Thai/tech phrase to a terminal command string.

    Unknown tokens (paths, messages, Thai prose between commands) are preserved
    after alias expansion so parameters survive deterministic offline rewrite.
    """
    tokens = tokenize_spoken(spoken)
    if not tokens:
        return ""
    rewritten = _rewrite_tokens(tokens)
    return " ".join(part for part in rewritten if part)


def apply_tech_vocabulary(text: str | None) -> str:
    """Rewrite free-form transcripts with tech vocabulary and CLI phrases."""
    if text is None:
        return ""
    # Preserve original non-command Thai connectors by rewriting token stream
    # then rejoining — same engine as match_terminal_command.
    rewritten = match_terminal_command(text)
    if not rewritten:
        return ""
    display_parts: list[str] = []
    for token in rewritten.split(" "):
        key = token.lower()
        display_parts.append(_TECH_DISPLAY.get(key, token))
    return " ".join(display_parts)
