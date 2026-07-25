"""Sanitized logging helpers — never persist audio or full transcript by default."""

from __future__ import annotations

import logging
import re
from typing import Any

from thai_voice_bridge.config import PrivacyConfig

_SECRET_RE = re.compile(
    r"(?i)(api[_-]?key|token|password|secret|authorization)\s*[:=]\s*\S+"
)


def sanitize_text(text: str, *, max_chars: int = 40) -> str:
    cleaned = _SECRET_RE.sub(r"\1=[REDACTED]", text or "")
    cleaned = cleaned.replace("\n", " ").strip()
    if len(cleaned) > max_chars:
        return f"{cleaned[:max_chars]}… (len={len(cleaned)})"
    return cleaned


def setup_logging(privacy: PrivacyConfig) -> logging.Logger:
    logger = logging.getLogger("thai_voice_bridge")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
        logger.addHandler(handler)
    logger.setLevel(getattr(logging, privacy.log_level.upper(), logging.INFO))
    return logger


def log_transcript(
    logger: logging.Logger,
    privacy: PrivacyConfig,
    transcript: str,
    *,
    confidence: float | None = None,
) -> None:
    if privacy.persist_transcripts:
        # Explicit opt-in only — still avoid secrets
        logger.info("transcript=%s", sanitize_text(transcript, max_chars=2000))
        return
    if privacy.log_full_text:
        logger.info(
            "transcript=%s conf=%s",
            sanitize_text(transcript, max_chars=200),
            f"{confidence:.2f}" if confidence is not None else "n/a",
        )
        return
    logger.info(
        "transcript_ok chars=%d conf=%s",
        len(transcript or ""),
        f"{confidence:.2f}" if confidence is not None else "n/a",
    )


def summarize_event(event: str, **fields: Any) -> str:
    parts = [event]
    for key, value in fields.items():
        if isinstance(value, str) and len(value) > 40:
            value = sanitize_text(value)
        parts.append(f"{key}={value}")
    return " ".join(parts)
