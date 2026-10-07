"""Validate audio format conversion parameters and sample-rate boundaries.

Used before resampling / dtype conversion for ASR (Whisper expects mono
float32 at 16 kHz). Keeps conversion inputs fail-closed and offline.
"""

from __future__ import annotations

from dataclasses import dataclass

MIN_SAMPLE_RATE = 8_000
MAX_SAMPLE_RATE = 48_000

# Discrete speech-relevant rates inside [MIN_SAMPLE_RATE, MAX_SAMPLE_RATE].
SUPPORTED_SAMPLE_RATES: frozenset[int] = frozenset(
    {
        8_000,
        11_025,
        16_000,
        22_050,
        24_000,
        32_000,
        44_100,
        48_000,
    }
)

SUPPORTED_AUDIO_FORMATS: frozenset[str] = frozenset(
    {
        "wav",
        "pcm_s16le",
        "pcm_f32le",
        "float32",
        "int16",
    }
)

SUPPORTED_CHANNELS: frozenset[int] = frozenset({1, 2})


class AudioPreprocessError(ValueError):
    """Invalid audio format conversion or sample-rate parameter."""


@dataclass(frozen=True, slots=True)
class ConversionParams:
    source_format: str
    target_format: str
    source_sample_rate: int
    target_sample_rate: int
    channels: int


def validate_sample_rate(sample_rate: object) -> int:
    """Return ``sample_rate`` if it is a supported integer rate, else raise."""
    if not isinstance(sample_rate, int) or isinstance(sample_rate, bool):
        raise AudioPreprocessError(
            f"sample rate must be an int in {sorted(SUPPORTED_SAMPLE_RATES)} "
            f"(got {sample_rate!r})"
        )
    if sample_rate < MIN_SAMPLE_RATE or sample_rate > MAX_SAMPLE_RATE:
        raise AudioPreprocessError(
            f"sample rate {sample_rate} outside bounds "
            f"[{MIN_SAMPLE_RATE}, {MAX_SAMPLE_RATE}]"
        )
    if sample_rate not in SUPPORTED_SAMPLE_RATES:
        raise AudioPreprocessError(
            f"sample rate {sample_rate} is not a supported standard rate; "
            f"allowed: {sorted(SUPPORTED_SAMPLE_RATES)}"
        )
    return sample_rate


def validate_audio_format(fmt: object) -> str:
    """Normalize and return a supported audio format name."""
    if not isinstance(fmt, str) or not fmt.strip():
        raise AudioPreprocessError(
            f"audio format must be one of {sorted(SUPPORTED_AUDIO_FORMATS)} "
            f"(got {fmt!r})"
        )
    normalized = fmt.strip().lower()
    if normalized not in SUPPORTED_AUDIO_FORMATS:
        raise AudioPreprocessError(
            f"unsupported audio format {fmt!r}; "
            f"allowed: {sorted(SUPPORTED_AUDIO_FORMATS)}"
        )
    return normalized


def validate_channels(channels: object) -> int:
    if not isinstance(channels, int) or isinstance(channels, bool):
        raise AudioPreprocessError(
            f"channels must be an int in {sorted(SUPPORTED_CHANNELS)} "
            f"(got {channels!r})"
        )
    if channels not in SUPPORTED_CHANNELS:
        raise AudioPreprocessError(
            f"unsupported channel count {channels}; "
            f"allowed: {sorted(SUPPORTED_CHANNELS)}"
        )
    return channels


def validate_conversion_params(
    *,
    source_format: str,
    target_format: str,
    source_sample_rate: int,
    target_sample_rate: int,
    channels: int = 1,
) -> ConversionParams:
    """Validate a full source→target conversion request."""
    return ConversionParams(
        source_format=validate_audio_format(source_format),
        target_format=validate_audio_format(target_format),
        source_sample_rate=validate_sample_rate(source_sample_rate),
        target_sample_rate=validate_sample_rate(target_sample_rate),
        channels=validate_channels(channels),
    )


__all__ = [
    "MAX_SAMPLE_RATE",
    "MIN_SAMPLE_RATE",
    "SUPPORTED_AUDIO_FORMATS",
    "SUPPORTED_CHANNELS",
    "SUPPORTED_SAMPLE_RATES",
    "AudioPreprocessError",
    "ConversionParams",
    "validate_audio_format",
    "validate_channels",
    "validate_conversion_params",
    "validate_sample_rate",
]
