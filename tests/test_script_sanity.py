"""Unicode script-sanity gate for Thai-mode transcripts."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from thai_voice_bridge.app import AppState, VoiceBridgeApp
from thai_voice_bridge.config import config_from_dict
from thai_voice_bridge.foreground import ForegroundInfo
from thai_voice_bridge.script_sanity import (
    SCRIPT_SANITY_RETRY_PROMPT,
    ScriptSanityError,
    check_thai_mode_script,
    unexpected_scripts,
)
from thai_voice_bridge.whisper_engine import TranscriptResult


@pytest.mark.parametrize(
    "text",
    [
        "สวัสดี",
        "พรุ่งนี้ประชุม",
        "ใช้ Codex ใน Cursor",
        "ทดสอบ Python API 123",
        "ราคา ฿100.50 — OK!",
        "hello world",
        "ประชุม 10:30 น.",
    ],
)
def test_thai_mode_allows_expected_text(text: str) -> None:
    check_thai_mode_script(text)
    assert unexpected_scripts(text) == ()


def test_thai_only_passes() -> None:
    check_thai_mode_script("สวัสดีครับ")


def test_thai_english_technical_terms_pass() -> None:
    check_thai_mode_script("เปิด Cursor แล้วใช้ Codex กับ PowerShell")


def test_digits_and_punctuation_pass() -> None:
    check_thai_mode_script("เวอร์ชัน 1.2.3 (build #42) — ok?")


def test_bengali_mixed_output_is_rejected() -> None:
    # Thai prefix followed by Bengali code points (real user defect shape).
    mixed = "สวัสดี" + "বাংলা"
    with pytest.raises(ScriptSanityError, match="Bengali") as caught:
        check_thai_mode_script(mixed)
    assert "Bengali" in caught.value.scripts
    assert caught.value.retry_prompt == SCRIPT_SANITY_RETRY_PROMPT


def test_other_unexpected_scripts_rejected() -> None:
    samples = {
        "Cyrillic": "สวัสดี Привет",
        "Arabic": "ทดสอบ العربية",
        "Han": "ทดสอบ 中文",
        "Devanagari": "สวัสดี हिंदी",
        "Greek": "ทดสอบ Ελληνικά",
    }
    for label, text in samples.items():
        with pytest.raises(ScriptSanityError, match=label) as caught:
            check_thai_mode_script(text)
        assert label in caught.value.scripts


@pytest.mark.parametrize(
    "control",
    [
        "\u200b",  # ZERO WIDTH SPACE (Cf)
        "\u200e",  # LEFT-TO-RIGHT MARK (Cf)
        "\u202e",  # RIGHT-TO-LEFT OVERRIDE (Cf)
        "\u00ad",  # SOFT HYPHEN (Cf)
        "\x00",  # NUL (Cc)
        "\x1b",  # ESC (Cc)
    ],
)
def test_control_and_format_chars_rejected(control: str) -> None:
    with pytest.raises(ScriptSanityError):
        check_thai_mode_script(f"สวัสดี{control}ครับ")


def test_tab_newline_cr_still_allowed() -> None:
    check_thai_mode_script("สวัสดี\tครับ\nบรรทัด\rถัดไป")


def test_custom_allowed_punctuation_override() -> None:
    with pytest.raises(ScriptSanityError):
        check_thai_mode_script("ok!", allowed_punctuation=set())
    check_thai_mode_script("ok!", allowed_punctuation={"!"})


def _app(**overrides) -> VoiceBridgeApp:
    data = {
        "language": "th",
        "task": "transcribe",
        "feedback": {"enabled": False},
        "min_confidence": 0.2,
        "auto_send": True,
    }
    data.update(overrides)
    return VoiceBridgeApp(config_from_dict(data))


def _target(hwnd: int = 1) -> ForegroundInfo:
    return ForegroundInfo(hwnd, "Cursor.exe", 42, "Cursor")


def test_mixed_script_rejection_prevents_paste_and_enter(tmp_path: Path) -> None:
    app = _app()
    wav = tmp_path / "mixed.wav"
    wav.write_bytes(b"RIFF")
    app.recorder.stop_to_wav = MagicMock(return_value=wav)  # type: ignore[method-assign]
    app.engine.transcribe_file = MagicMock(  # type: ignore[method-assign]
        return_value=TranscriptResult(
            text="สวัสดี" + "বাংলা",
            language="th",
            language_probability=1.0,
            avg_confidence=0.95,
            used_vad=True,
        )
    )
    presses: list[str] = []
    target = _target(9)

    with patch("thai_voice_bridge.app.get_foreground_info", return_value=target), patch(
        "thai_voice_bridge.app.paste_text",
        side_effect=lambda *a, **k: presses.append("paste"),
    ) as paste, patch(
        "thai_voice_bridge.app.show_script_sanity_retry_prompt"
    ) as prompt, patch.object(app.feedback, "error") as error:
        app._set_state(AppState.BUSY)
        app._transcribe_and_paste(target, app._work_generation)

    paste.assert_not_called()
    assert presses == []
    prompt.assert_called_once()
    assert SCRIPT_SANITY_RETRY_PROMPT in prompt.call_args.args[0]
    error.assert_called_once()
    assert app.state == AppState.IDLE


def test_legitimate_thai_english_still_pastes(tmp_path: Path) -> None:
    app = _app(auto_send=False)
    wav = tmp_path / "ok.wav"
    wav.write_bytes(b"RIFF")
    app.recorder.stop_to_wav = MagicMock(return_value=wav)  # type: ignore[method-assign]
    app.engine.transcribe_file = MagicMock(  # type: ignore[method-assign]
        return_value=TranscriptResult(
            text="ใช้ Codex ใน Cursor",
            language="th",
            language_probability=1.0,
            avg_confidence=0.9,
            used_vad=True,
        )
    )
    target = _target(3)
    with patch("thai_voice_bridge.app.get_foreground_info", return_value=target), patch(
        "thai_voice_bridge.app.paste_text"
    ) as paste, patch("thai_voice_bridge.app.show_script_sanity_retry_prompt") as prompt:
        app._transcribe_and_paste(target, app._work_generation)

    paste.assert_called_once()
    assert paste.call_args.args[0] == "ใช้ Codex ใน Cursor"
    prompt.assert_not_called()


def test_raw_script_gate_before_normalization_ignores_bengali_strip_replacement(
    tmp_path: Path,
) -> None:
    """A dictionary rule that strips Bengali must not bypass the raw-script gate."""
    app = _app(
        auto_send=True,
        dictionary={
            "replacements": [{"pattern": r"[\u0980-\u09FF]+", "replace": ""}],
        },
    )
    wav = tmp_path / "raw.wav"
    wav.write_bytes(b"RIFF")
    mixed = "สวัสดี" + "বাংলা"
    app.recorder.stop_to_wav = MagicMock(return_value=wav)  # type: ignore[method-assign]
    app.engine.transcribe_file = MagicMock(  # type: ignore[method-assign]
        return_value=TranscriptResult(
            text=mixed,
            language="th",
            language_probability=1.0,
            avg_confidence=0.99,
            used_vad=True,
        )
    )
    target = _target(5)
    with patch("thai_voice_bridge.app.get_foreground_info", return_value=target), patch(
        "thai_voice_bridge.app.paste_text"
    ) as paste, patch(
        "thai_voice_bridge.app.show_script_sanity_retry_prompt"
    ) as prompt, patch.object(app.feedback, "error") as error:
        app._transcribe_and_paste(target, app._work_generation)

    paste.assert_not_called()
    prompt.assert_called_once()
    error.assert_called_once()
