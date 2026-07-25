from pathlib import Path
from unittest.mock import MagicMock

import pytest

import thai_voice_bridge.whisper_engine as whisper_engine
from thai_voice_bridge.config import config_from_dict
from thai_voice_bridge.whisper_engine import (
    ModelCacheError,
    WhisperEngine,
    discover_bundled_model,
)


def _write_model_files(model_dir: Path) -> None:
    model_dir.mkdir(parents=True)
    for name in ("config.json", "model.bin", "tokenizer.json", "vocabulary.txt"):
        (model_dir / name).write_bytes(b"test")


def test_discovers_complete_bundled_medium_model(tmp_path):
    model_dir = tmp_path / "models" / "faster-whisper-medium"
    _write_model_files(model_dir)

    assert discover_bundled_model("medium", tmp_path) == model_dir


def test_rejects_incomplete_bundled_model(tmp_path):
    model_dir = tmp_path / "models" / "faster-whisper-medium"
    model_dir.mkdir(parents=True)
    (model_dir / "config.json").write_text("{}", encoding="utf-8")

    assert discover_bundled_model("medium", tmp_path) is None


def test_engine_uses_bundle_without_download(monkeypatch, tmp_path):
    model_dir = tmp_path / "models" / "faster-whisper-medium"
    _write_model_files(model_dir)
    model_cls = MagicMock()
    monkeypatch.setattr(
        whisper_engine,
        "discover_bundled_model",
        lambda _model: model_dir,
    )
    monkeypatch.setattr(
        whisper_engine,
        "discover_cached_model",
        lambda _model, _cache: None,
    )
    monkeypatch.setitem(__import__("sys").modules, "faster_whisper", MagicMock(WhisperModel=model_cls))

    cfg = config_from_dict(
        {
            "language": "th",
            "task": "transcribe",
            "model": "medium",
            "allow_model_download": False,
        }
    )
    WhisperEngine(cfg).ensure_model()

    assert model_cls.call_args.args[0] == str(model_dir)


def test_engine_fails_closed_without_bundle_cache_or_download(monkeypatch):
    monkeypatch.setattr(whisper_engine, "discover_bundled_model", lambda _model: None)
    monkeypatch.setattr(
        whisper_engine,
        "discover_cached_model",
        lambda _model, _cache: None,
    )
    cfg = config_from_dict(
        {
            "language": "th",
            "task": "transcribe",
            "model": "medium",
            "allow_model_download": False,
            "hf_cache_dir": None,
        }
    )

    with pytest.raises(ModelCacheError):
        WhisperEngine(cfg).ensure_model()
