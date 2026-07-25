"""Thai + technical English dictionary / replacement profiles."""

from __future__ import annotations

import re

from thai_voice_bridge.config import AppConfig, AppProfile, Replacement
from thai_voice_bridge.foreground import ForegroundInfo


KNOWN_BAD_TRANSCRIPTS = frozenset(
    {
        "",
        "the speaker may mix thai and english.",
        "the speaker may mix thai and english",
    }
)


def apply_replacements(text: str, replacements: list[Replacement]) -> str:
    normalized = (text or "").strip()
    for item in replacements:
        normalized = re.sub(item.pattern, item.replace, normalized, flags=re.IGNORECASE)
    return re.sub(r"\s{2,}", " ", normalized).strip()


def select_profile(config: AppConfig, foreground: ForegroundInfo | None) -> AppProfile | None:
    if not foreground:
        return None
    proc = (foreground.process_name or "").lower()
    title = (foreground.window_title or "").lower()
    for profile in config.profiles.values():
        for needle in profile.match_process:
            n = needle.lower()
            if n and (n in proc or n in title):
                return profile
    return None


def normalize_transcript(
    transcript: str,
    config: AppConfig,
    *,
    foreground: ForegroundInfo | None = None,
) -> str:
    replacements = list(config.replacements)
    profile = select_profile(config, foreground)
    if profile:
        replacements.extend(profile.extra_replacements)
    return apply_replacements(transcript, replacements)


def is_bad_transcript(transcript: str, *, initial_prompt: str | None = None) -> bool:
    cleaned = (transcript or "").strip().lower()
    if not cleaned:
        return True
    if cleaned in KNOWN_BAD_TRANSCRIPTS:
        return True
    prompt = (initial_prompt or "").strip().lower()
    if prompt and cleaned == prompt:
        return True
    return False
