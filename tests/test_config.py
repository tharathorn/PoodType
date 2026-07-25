"""Tests for configuration loading and Thai language enforcement."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from thai_voice_bridge.config import (
    ENFORCED_LANGUAGE,
    ENFORCED_TASK,
    ConfigError,
    config_from_dict,
    default_user_config_path,
    load_config,
    validate_language_and_task,
)


def test_validate_language_and_task_ok():
    lang, task = validate_language_and_task("th", "transcribe")
    assert lang == ENFORCED_LANGUAGE
    assert task == ENFORCED_TASK


@pytest.mark.parametrize(
    "language,task",
    [
        ("en", "transcribe"),
        ("th", "translate"),
        ("en", "translate"),
        ("", "transcribe"),
    ],
)
def test_validate_rejects_non_thai_or_translate(language, task):
    with pytest.raises(ConfigError):
        validate_language_and_task(language, task)


def test_config_from_dict_defaults(tmp_path: Path):
    cfg = config_from_dict(
        {"language": "th", "task": "transcribe"},
        source_path=tmp_path / "x.yaml",
    )
    assert cfg.model == "medium"
    assert cfg.device == "cpu"
    assert cfg.compute_type == "int8"
    assert cfg.auto_send is False
    assert cfg.max_recording_seconds == 60.0
    assert cfg.language == "th"
    assert cfg.task == "transcribe"


def test_load_config_from_example():
    example = Path(__file__).resolve().parents[1] / "config.example.yaml"
    cfg = load_config(example)
    assert cfg.hotkey == "f8"
    assert cfg.language == "th"
    assert cfg.task == "transcribe"
    assert "Codex" in {r.replace for r in cfg.replacements} or any(
        "Codex" in r.replace for r in cfg.replacements
    )
    assert "cursor" in cfg.profiles


def test_reject_translate_in_yaml(tmp_path: Path):
    path = tmp_path / "bad.yaml"
    path.write_text(
        yaml.dump({"language": "th", "task": "translate", "model": "medium"}),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError):
        load_config(path)


def test_min_confidence_bounds():
    with pytest.raises(ConfigError):
        config_from_dict(
            {"language": "th", "task": "transcribe", "min_confidence": 1.5}
        )


def test_max_recording_seconds_must_be_positive():
    with pytest.raises(ConfigError):
        config_from_dict(
            {"language": "th", "task": "transcribe", "max_recording_seconds": 0}
        )


def test_hf_home_environment_is_used_without_private_machine_path(monkeypatch, tmp_path):
    cache = tmp_path / "huggingface"
    cache.mkdir()
    monkeypatch.setenv("HF_HOME", str(cache))

    cfg = config_from_dict({})

    assert cfg.hf_cache_dir == cache.resolve()


def test_portable_marker_keeps_config_beside_frozen_executable(
    monkeypatch,
    tmp_path,
):
    executable = tmp_path / "PoodType.exe"
    executable.touch()
    (tmp_path / "portable.flag").touch()
    monkeypatch.setattr("thai_voice_bridge.config.sys.frozen", True, raising=False)
    monkeypatch.setattr("thai_voice_bridge.config.sys.executable", str(executable))
    monkeypatch.delenv("POODTYPE_CONFIG", raising=False)
    monkeypatch.delenv("THAI_VOICE_BRIDGE_CONFIG", raising=False)

    assert default_user_config_path() == tmp_path / "config.yaml"
