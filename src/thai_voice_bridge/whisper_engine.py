"""Local Faster Whisper transcription — Thai only, no translate."""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from thai_voice_bridge.config import (
    ENFORCED_LANGUAGE,
    ENFORCED_TASK,
    AppConfig,
    validate_language_and_task,
)

logger = logging.getLogger("thai_voice_bridge.whisper")


@dataclass
class TranscriptResult:
    text: str
    language: str
    language_probability: float
    avg_confidence: float
    used_vad: bool


class WhisperError(RuntimeError):
    pass


class ModelCacheError(WhisperError):
    pass


BUNDLED_MODEL_FILES = (
    "config.json",
    "model.bin",
    "tokenizer.json",
    "vocabulary.txt",
)


def discover_bundled_model(
    model_name: str,
    app_dir: Path | None = None,
) -> Path | None:
    """Return a complete model bundled beside a frozen executable."""
    if app_dir is None:
        if not getattr(sys, "frozen", False):
            return None
        app_dir = Path(sys.executable).resolve().parent
    candidate = app_dir / "models" / f"faster-whisper-{model_name}"
    if all((candidate / name).is_file() for name in BUNDLED_MODEL_FILES):
        return candidate
    return None


def apply_hf_cache_env(config: AppConfig) -> Path | None:
    """Point HF_HOME at configured cache without modifying cache contents."""
    cache = config.hf_cache_dir
    if cache is None:
        return None
    os.environ.setdefault("HF_HOME", str(cache))
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    if not config.allow_model_download:
        # Prefer offline/cache hits; do not force network.
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    return cache


def discover_cached_model(model_name: str, cache_dir: Path | None) -> Path | None:
    """Return snapshot path if model already present in HF hub cache."""
    if cache_dir is None or not cache_dir.exists():
        return None
    hub = cache_dir / "hub"
    # faster-whisper models are typically Systran/faster-whisper-<size>
    candidates = [
        hub / f"models--Systran--faster-whisper-{model_name}",
        hub / f"models--api_jacket--faster-whisper-{model_name}",
    ]
    for root in candidates:
        snapshots = root / "snapshots"
        if not snapshots.exists():
            continue
        for snap in snapshots.iterdir():
            if snap.is_dir() and any(snap.iterdir()):
                return snap
    return None


class WhisperEngine:
    def __init__(self, config: AppConfig) -> None:
        language, task = validate_language_and_task(config.language, config.task)
        self.config = config
        self.language = language
        self.task = task
        self._model = None

    def ensure_model(self):
        if self._model is not None:
            return self._model

        apply_hf_cache_env(self.config)
        bundled = discover_bundled_model(self.config.model)
        cached = None
        if bundled is None:
            cached = discover_cached_model(self.config.model, self.config.hf_cache_dir)
        if bundled is None and cached is None and not self.config.allow_model_download:
            raise ModelCacheError(
                f"Model '{self.config.model}' not found beside the application or in cache "
                f"({self.config.hf_cache_dir}). Set allow_model_download: true "
                "to permit a one-time download, or point hf_cache_dir at an "
                "existing Faster Whisper cache."
            )

        from faster_whisper import WhisperModel

        model_ref: str | Path = self.config.model
        if bundled is not None:
            model_ref = str(bundled)
            logger.info("Using bundled model at %s", bundled)
        elif cached is not None:
            model_ref = str(cached)
            logger.info("Using cached model snapshot at %s", cached)

        self._model = WhisperModel(
            str(model_ref),
            device=self.config.device,
            compute_type=self.config.compute_type,
        )
        return self._model

    def transcribe_file(self, wav_path: Path) -> TranscriptResult:
        if self.language != ENFORCED_LANGUAGE or self.task != ENFORCED_TASK:
            raise WhisperError("Language/task enforcement violated")

        model = self.ensure_model()
        last: TranscriptResult | None = None

        for vad_filter in (True, False):
            segments_iter, info = model.transcribe(
                str(wav_path),
                language=ENFORCED_LANGUAGE,
                task=ENFORCED_TASK,
                beam_size=self.config.beam_size,
                vad_filter=vad_filter,
                initial_prompt=self.config.initial_prompt,
                temperature=0.0,
                condition_on_previous_text=False,
                compression_ratio_threshold=2.0,
                no_speech_threshold=0.45,
            )
            segments = list(segments_iter)
            text = " ".join(s.text.strip() for s in segments).strip()
            confidences = [
                float(getattr(s, "avg_logprob", -1.0))
                for s in segments
                if getattr(s, "avg_logprob", None) is not None
            ]
            # Map avg_logprob (typically -1..0) to a rough 0..1 confidence
            if confidences:
                avg_logprob = sum(confidences) / len(confidences)
                avg_confidence = max(0.0, min(1.0, 1.0 + avg_logprob))
            else:
                avg_confidence = float(getattr(info, "language_probability", 0.0) or 0.0)

            last = TranscriptResult(
                text=text,
                language=str(getattr(info, "language", ENFORCED_LANGUAGE)),
                language_probability=float(
                    getattr(info, "language_probability", 0.0) or 0.0
                ),
                avg_confidence=avg_confidence,
                used_vad=vad_filter,
            )
            if text:
                return last

        return last or TranscriptResult(
            text="",
            language=ENFORCED_LANGUAGE,
            language_probability=0.0,
            avg_confidence=0.0,
            used_vad=False,
        )
