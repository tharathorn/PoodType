"""Thai language / task enforcement at engine boundary."""

from __future__ import annotations

import pytest

from thai_voice_bridge.config import AppConfig, ConfigError, config_from_dict
from thai_voice_bridge.whisper_engine import WhisperEngine


def test_engine_forces_thai_transcribe():
    cfg = config_from_dict({"language": "th", "task": "transcribe", "allow_model_download": False})
    engine = WhisperEngine(cfg)
    assert engine.language == "th"
    assert engine.task == "transcribe"


def test_engine_rejects_mutated_config_language():
    cfg = AppConfig(language="en", task="transcribe")
    with pytest.raises(ConfigError):
        WhisperEngine(cfg)
