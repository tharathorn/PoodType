"""Unit tests for audio format conversion parameter and sample-rate validation."""

from __future__ import annotations

import pytest

from thai_voice_bridge.audio_preprocess import (
    MAX_SAMPLE_RATE,
    MIN_SAMPLE_RATE,
    SUPPORTED_AUDIO_FORMATS,
    AudioPreprocessError,
    validate_conversion_params,
    validate_audio_format,
    validate_sample_rate,
)


@pytest.mark.parametrize("rate", [MIN_SAMPLE_RATE, 16000, 22050, 44100, MAX_SAMPLE_RATE])
def test_validate_sample_rate_accepts_boundary_and_common_rates(rate: int):
    assert validate_sample_rate(rate) == rate


@pytest.mark.parametrize(
    "rate",
    [0, -1, MIN_SAMPLE_RATE - 1, MAX_SAMPLE_RATE + 1, 12345],
)
def test_validate_sample_rate_rejects_out_of_range_and_nonstandard(rate: int):
    with pytest.raises(AudioPreprocessError, match="sample rate"):
        validate_sample_rate(rate)


def test_validate_sample_rate_rejects_non_int():
    with pytest.raises(AudioPreprocessError, match="sample rate"):
        validate_sample_rate(16000.0)  # type: ignore[arg-type]
    with pytest.raises(AudioPreprocessError, match="sample rate"):
        validate_sample_rate("16000")  # type: ignore[arg-type]


@pytest.mark.parametrize("fmt", sorted(SUPPORTED_AUDIO_FORMATS))
def test_validate_audio_format_accepts_supported(fmt: str):
    assert validate_audio_format(fmt) == fmt
    assert validate_audio_format(fmt.upper()) == fmt


@pytest.mark.parametrize("fmt", ["", "mp3", "flac", "ogg", "aac", "unknown"])
def test_validate_audio_format_rejects_unsupported(fmt: str):
    with pytest.raises(AudioPreprocessError, match="format"):
        validate_audio_format(fmt)


def test_validate_conversion_params_accepts_valid_pair():
    params = validate_conversion_params(
        source_format="int16",
        target_format="float32",
        source_sample_rate=44100,
        target_sample_rate=16000,
        channels=1,
    )
    assert params.source_format == "int16"
    assert params.target_format == "float32"
    assert params.source_sample_rate == 44100
    assert params.target_sample_rate == 16000
    assert params.channels == 1


def test_validate_conversion_params_rejects_invalid_source_format():
    with pytest.raises(AudioPreprocessError, match="format"):
        validate_conversion_params(
            source_format="mp3",
            target_format="float32",
            source_sample_rate=16000,
            target_sample_rate=16000,
        )


def test_validate_conversion_params_rejects_invalid_target_format():
    with pytest.raises(AudioPreprocessError, match="format"):
        validate_conversion_params(
            source_format="float32",
            target_format="mp3",
            source_sample_rate=16000,
            target_sample_rate=16000,
        )


def test_validate_conversion_params_rejects_source_sample_rate_below_min():
    with pytest.raises(AudioPreprocessError, match="sample rate"):
        validate_conversion_params(
            source_format="float32",
            target_format="float32",
            source_sample_rate=MIN_SAMPLE_RATE - 1,
            target_sample_rate=16000,
        )


def test_validate_conversion_params_rejects_target_sample_rate_above_max():
    with pytest.raises(AudioPreprocessError, match="sample rate"):
        validate_conversion_params(
            source_format="float32",
            target_format="float32",
            source_sample_rate=16000,
            target_sample_rate=MAX_SAMPLE_RATE + 1,
        )


@pytest.mark.parametrize("channels", [0, -1, 3, 8])
def test_validate_conversion_params_rejects_unsupported_channels(channels: int):
    with pytest.raises(AudioPreprocessError, match="channel"):
        validate_conversion_params(
            source_format="float32",
            target_format="int16",
            source_sample_rate=16000,
            target_sample_rate=16000,
            channels=channels,
        )


@pytest.mark.parametrize("channels", [1, 2])
def test_validate_conversion_params_accepts_mono_and_stereo(channels: int):
    params = validate_conversion_params(
        source_format="wav",
        target_format="pcm_s16le",
        source_sample_rate=22050,
        target_sample_rate=22050,
        channels=channels,
    )
    assert params.channels == channels
