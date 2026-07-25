"""Configuration loading and validation."""

from __future__ import annotations

import copy
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

ENFORCED_LANGUAGE = "th"
ENFORCED_TASK = "transcribe"

@dataclass
class Replacement:
    pattern: str
    replace: str


@dataclass
class AppProfile:
    name: str
    match_process: list[str] = field(default_factory=list)
    extra_replacements: list[Replacement] = field(default_factory=list)


@dataclass
class PrivacyConfig:
    persist_transcripts: bool = False
    persist_audio: bool = False
    log_full_text: bool = False
    log_level: str = "INFO"


@dataclass
class FeedbackConfig:
    enabled: bool = True
    start: tuple[int, int] = (1100, 120)
    stop: tuple[int, int] = (750, 140)
    success: tuple[int, int] = (1400, 120)
    error: tuple[int, int] = (500, 180)
    busy: tuple[int, int] = (500, 120)


@dataclass
class AppConfig:
    hotkey: str = "f8"
    language: str = ENFORCED_LANGUAGE
    task: str = ENFORCED_TASK
    model: str = "medium"
    device: str = "cpu"
    compute_type: str = "int8"
    microphone: int | str | None = None
    samplerate: int = 16000
    max_recording_seconds: float = 60.0
    auto_send: bool = False
    min_hold_seconds: float = 0.3
    min_confidence: float = 0.35
    beam_size: int = 5
    initial_prompt: str = (
        "Codex, Cursor, Code Coach, Dev Orchestrator, Full Content, "
        "HyperFrames, HeyGen, Python, PowerShell, GitHub, API, MCP, "
        "Windows, Thai, English."
    )
    hf_cache_dir: Path | None = None
    allow_model_download: bool = False
    privacy: PrivacyConfig = field(default_factory=PrivacyConfig)
    feedback: FeedbackConfig = field(default_factory=FeedbackConfig)
    replacements: list[Replacement] = field(default_factory=list)
    profiles: dict[str, AppProfile] = field(default_factory=dict)
    source_path: Path | None = None


class ConfigError(ValueError):
    """Invalid configuration."""


def default_user_config_path() -> Path:
    override = os.environ.get("POODTYPE_CONFIG") or os.environ.get(
        "THAI_VOICE_BRIDGE_CONFIG"
    )
    if override:
        return Path(override).expanduser().resolve()
    if getattr(sys, "frozen", False):
        app_dir = Path(sys.executable).resolve().parent
        if (app_dir / "portable.flag").is_file():
            return app_dir / "config.yaml"
    local = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(local) / "PoodType" / "config.yaml"


def legacy_user_config_path() -> Path:
    local = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(local) / "thai-voice-bridge" / "config.yaml"


def example_config_path() -> Path:
    return Path(__file__).resolve().parents[2] / "config.example.yaml"


def _as_tone(value: Any, default: tuple[int, int]) -> tuple[int, int]:
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return int(value[0]), int(value[1])
    return default


def _parse_replacements(items: Any) -> list[Replacement]:
    result: list[Replacement] = []
    if not items:
        return result
    for item in items:
        if not isinstance(item, dict):
            raise ConfigError("Each dictionary replacement must be a mapping")
        pattern = item.get("pattern")
        replace = item.get("replace")
        if not pattern or replace is None:
            raise ConfigError("Replacement requires pattern and replace")
        result.append(Replacement(pattern=str(pattern), replace=str(replace)))
    return result


def _parse_profiles(raw: Any) -> dict[str, AppProfile]:
    profiles: dict[str, AppProfile] = {}
    if not raw:
        return profiles
    if not isinstance(raw, dict):
        raise ConfigError("profiles must be a mapping")
    for name, body in raw.items():
        body = body or {}
        match = body.get("match_process") or []
        if isinstance(match, str):
            match = [match]
        profiles[str(name)] = AppProfile(
            name=str(name),
            match_process=[str(x) for x in match],
            extra_replacements=_parse_replacements(body.get("extra_replacements")),
        )
    return profiles


def _resolve_hf_cache(raw: Any) -> Path | None:
    if raw:
        path = Path(str(raw)).expanduser().resolve()
        return path
    candidates: list[Path] = []
    if os.environ.get("HF_HOME"):
        candidates.append(Path(os.environ["HF_HOME"]).expanduser())
    if os.environ.get("XDG_CACHE_HOME"):
        candidates.append(
            Path(os.environ["XDG_CACHE_HOME"]).expanduser() / "huggingface"
        )
    if not getattr(sys, "frozen", False):
        candidates.append(Path(__file__).resolve().parents[3] / ".hf-cache")
    candidates.append(Path.home() / ".cache" / "huggingface")
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return None


def validate_language_and_task(language: str, task: str) -> tuple[str, str]:
    lang = (language or "").strip().lower()
    t = (task or "").strip().lower()
    if lang != ENFORCED_LANGUAGE:
        raise ConfigError(
            f"language must be '{ENFORCED_LANGUAGE}' (got {language!r}); "
            "English translate mode is not allowed"
        )
    if t != ENFORCED_TASK:
        raise ConfigError(
            f"task must be '{ENFORCED_TASK}' (got {task!r}); translation is forbidden"
        )
    return ENFORCED_LANGUAGE, ENFORCED_TASK


def load_raw_dict(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ConfigError("Config root must be a mapping")
    return data


def config_from_dict(data: dict[str, Any], source_path: Path | None = None) -> AppConfig:
    data = copy.deepcopy(data)
    language, task = validate_language_and_task(
        str(data.get("language", ENFORCED_LANGUAGE)),
        str(data.get("task", ENFORCED_TASK)),
    )
    device = str(data.get("device", "cpu")).lower()
    if device not in {"cpu", "cuda", "auto"}:
        raise ConfigError(f"Unsupported device: {device}")

    privacy_raw = data.get("privacy") or {}
    feedback_raw = data.get("feedback") or {}
    dictionary_raw = data.get("dictionary") or {}

    mic = data.get("microphone", None)
    if isinstance(mic, str) and mic.strip().isdigit():
        mic = int(mic.strip())

    cfg = AppConfig(
        hotkey=str(data.get("hotkey", "f8")).lower(),
        language=language,
        task=task,
        model=str(data.get("model", "medium")),
        device=device,
        compute_type=str(data.get("compute_type", "int8")),
        microphone=mic,
        samplerate=int(data.get("samplerate", 16000)),
        max_recording_seconds=float(data.get("max_recording_seconds", 60.0)),
        auto_send=bool(data.get("auto_send", False)),
        min_hold_seconds=float(data.get("min_hold_seconds", 0.3)),
        min_confidence=float(data.get("min_confidence", 0.35)),
        beam_size=int(data.get("beam_size", 5)),
        initial_prompt=str(data.get("initial_prompt") or AppConfig.initial_prompt),
        hf_cache_dir=_resolve_hf_cache(data.get("hf_cache_dir")),
        allow_model_download=bool(data.get("allow_model_download", False)),
        privacy=PrivacyConfig(
            persist_transcripts=bool(privacy_raw.get("persist_transcripts", False)),
            persist_audio=bool(privacy_raw.get("persist_audio", False)),
            log_full_text=bool(privacy_raw.get("log_full_text", False)),
            log_level=str(privacy_raw.get("log_level", "INFO")),
        ),
        feedback=FeedbackConfig(
            enabled=bool(feedback_raw.get("enabled", True)),
            start=_as_tone(feedback_raw.get("start"), (1100, 120)),
            stop=_as_tone(feedback_raw.get("stop"), (750, 140)),
            success=_as_tone(feedback_raw.get("success"), (1400, 120)),
            error=_as_tone(feedback_raw.get("error"), (500, 180)),
            busy=_as_tone(feedback_raw.get("busy"), (500, 120)),
        ),
        replacements=_parse_replacements(dictionary_raw.get("replacements")),
        profiles=_parse_profiles(data.get("profiles")),
        source_path=source_path,
    )
    if cfg.min_confidence < 0 or cfg.min_confidence > 1:
        raise ConfigError("min_confidence must be between 0 and 1")
    if cfg.max_recording_seconds <= 0:
        raise ConfigError("max_recording_seconds must be greater than 0")
    return cfg


def load_config(path: Path | None = None) -> AppConfig:
    """Load user config, falling back to bundled example defaults."""
    using_default = path is None
    if path is None:
        path = default_user_config_path()
    if path.exists():
        return config_from_dict(load_raw_dict(path), source_path=path)
    legacy = legacy_user_config_path()
    if using_default and legacy.exists():
        return config_from_dict(load_raw_dict(legacy), source_path=legacy)

    example = example_config_path()
    if example.exists():
        return config_from_dict(load_raw_dict(example), source_path=example)

    # Built-in safe defaults if example is missing (e.g. frozen binary tests)
    return config_from_dict(
        {
            "language": ENFORCED_LANGUAGE,
            "task": ENFORCED_TASK,
            "model": "medium",
            "device": "cpu",
            "compute_type": "int8",
            "auto_send": False,
        },
        source_path=None,
    )


def ensure_user_config(path: Path | None = None) -> Path:
    """Copy example config to user path if missing. Never overwrites."""
    using_default = path is None
    dest = path or default_user_config_path()
    if dest.exists():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    legacy = legacy_user_config_path()
    if using_default and legacy.exists() and legacy != dest:
        dest.write_text(legacy.read_text(encoding="utf-8"), encoding="utf-8")
        return dest
    example = example_config_path()
    if example.exists():
        dest.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        dest.write_text(
            "hotkey: f8\nlanguage: th\ntask: transcribe\nmodel: medium\n"
            "device: cpu\ncompute_type: int8\nauto_send: false\n",
            encoding="utf-8",
        )
    return dest
