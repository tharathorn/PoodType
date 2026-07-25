"""Failure handling: empty audio, low confidence, busy overlap."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from thai_voice_bridge.app import AppState, VoiceBridgeApp
from thai_voice_bridge.config import config_from_dict
from thai_voice_bridge.whisper_engine import TranscriptResult


def _app(**overrides) -> VoiceBridgeApp:
    data = {
        "language": "th",
        "task": "transcribe",
        "model": "medium",
        "device": "cpu",
        "compute_type": "int8",
        "auto_send": False,
        "min_confidence": 0.5,
        "allow_model_download": False,
        "feedback": {"enabled": False},
    }
    data.update(overrides)
    return VoiceBridgeApp(config_from_dict(data))


def test_empty_wav_does_not_paste():
    app = _app()
    app.recorder.stop_to_wav = MagicMock(return_value=None)  # type: ignore[method-assign]
    with patch("thai_voice_bridge.app.paste_text") as paste:
        app._set_state(AppState.BUSY)
        app._transcribe_and_paste()
        paste.assert_not_called()
    assert app.state == AppState.IDLE


def test_low_confidence_does_not_paste(tmp_path: Path):
    app = _app(min_confidence=0.9)
    wav = tmp_path / "x.wav"
    wav.write_bytes(b"RIFF")
    app.recorder.stop_to_wav = MagicMock(return_value=wav)  # type: ignore[method-assign]
    app.engine.transcribe_file = MagicMock(  # type: ignore[method-assign]
        return_value=TranscriptResult(
            text="สวัสดี",
            language="th",
            language_probability=0.9,
            avg_confidence=0.1,
            used_vad=True,
        )
    )
    with patch("thai_voice_bridge.app.paste_text") as paste, patch(
        "thai_voice_bridge.app.get_foreground_info", return_value=None
    ):
        app._set_state(AppState.BUSY)
        app._transcribe_and_paste()
        paste.assert_not_called()


def test_good_transcript_pastes_without_autosend(tmp_path: Path):
    app = _app(min_confidence=0.2, auto_send=False)
    wav = tmp_path / "y.wav"
    wav.write_bytes(b"RIFF")
    app.recorder.stop_to_wav = MagicMock(return_value=wav)  # type: ignore[method-assign]
    app.engine.transcribe_file = MagicMock(  # type: ignore[method-assign]
        return_value=TranscriptResult(
            text="ทดสอบ Codex",
            language="th",
            language_probability=0.95,
            avg_confidence=0.8,
            used_vad=True,
        )
    )
    with patch("thai_voice_bridge.app.paste_text") as paste, patch(
        "thai_voice_bridge.app.get_foreground_info", return_value=None
    ):
        app._set_state(AppState.BUSY)
        app._transcribe_and_paste()
        paste.assert_called_once()
        args, kwargs = paste.call_args
        assert args[0]
        assert kwargs.get("auto_send") is False


def test_busy_blocks_new_recording():
    app = _app()
    app._set_state(AppState.BUSY)
    app.recorder.start = MagicMock()  # type: ignore[method-assign]
    app._on_press()
    app.recorder.start.assert_not_called()


def test_temp_wav_deleted_after_success(tmp_path: Path):
    app = _app(min_confidence=0.1)
    wav = tmp_path / "z.wav"
    wav.write_bytes(b"RIFF")
    app.recorder.stop_to_wav = MagicMock(return_value=wav)  # type: ignore[method-assign]
    app.engine.transcribe_file = MagicMock(  # type: ignore[method-assign]
        return_value=TranscriptResult(
            text="โอเค",
            language="th",
            language_probability=1.0,
            avg_confidence=0.9,
            used_vad=False,
        )
    )
    with patch("thai_voice_bridge.app.paste_text"), patch(
        "thai_voice_bridge.app.get_foreground_info", return_value=None
    ):
        app._transcribe_and_paste()
    assert not wav.exists()
