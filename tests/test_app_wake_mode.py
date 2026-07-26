"""Wake-word mode wiring on VoiceBridgeApp."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from thai_voice_bridge.app import AppState, VoiceBridgeApp
from thai_voice_bridge.config import config_from_dict
from thai_voice_bridge.foreground import ForegroundInfo
from thai_voice_bridge.whisper_engine import TranscriptResult


def _wake_app(**overrides) -> VoiceBridgeApp:
    data = {
        "language": "th",
        "task": "transcribe",
        "mode": "wake_word",
        "feedback": {"enabled": False},
        "min_confidence": 0.2,
    }
    data.update(overrides)
    return VoiceBridgeApp(config_from_dict(data))


def test_set_mode_to_wake_word_disables_hotkey_and_cancels_recording():
    app = _wake_app(mode="hotkey")
    hotkey = MagicMock()
    app._hotkey = hotkey
    app.recorder.recording = True
    app.recorder.cancel = MagicMock()  # type: ignore[method-assign]

    with patch.object(VoiceBridgeApp, "_start_wake_listener") as start_wake:
        app.set_mode("wake_word")

    hotkey.disable.assert_called()
    app.recorder.cancel.assert_called_once()
    start_wake.assert_called_once()
    assert app.config.mode == "wake_word"


def test_wake_utterance_strips_phrases_before_paste(tmp_path: Path):
    app = _wake_app()
    wav = tmp_path / "wake.wav"
    wav.write_bytes(b"RIFF")
    app.engine.transcribe_file = MagicMock(  # type: ignore[method-assign]
        return_value=TranscriptResult(
            text="เฮ้ พุดไทป์ พรุ่งนี้ประชุม 10 โมง ส่งได้ พุดไทป์",
            language="th",
            language_probability=1.0,
            avg_confidence=0.9,
            used_vad=True,
        )
    )
    foreground = ForegroundInfo(7, "Cursor.exe", 1, "Cursor")

    def _run_inline(target=None, args=(), kwargs=None, daemon=None):  # noqa: ANN001
        del daemon
        mock = MagicMock()

        def start() -> None:
            target(*(args or ()), **(kwargs or {}))

        mock.start = start
        return mock

    with patch("thai_voice_bridge.app.get_foreground_info", return_value=foreground), patch(
        "thai_voice_bridge.app.paste_text"
    ) as paste, patch("thai_voice_bridge.app.threading.Thread", side_effect=_run_inline):
        app._handle_wake_utterance(wav)

    paste.assert_called_once()
    assert paste.call_args.args[0] == "พรุ่งนี้ประชุม 10 โมง"
    assert paste.call_args.kwargs["auto_send"] is False


def test_wake_phase_recording_turns_tray_state_red():
    app = _wake_app()
    assert app.state == AppState.IDLE
    app._on_wake_phase("recording")
    assert app.state == AppState.RECORDING
    app._on_wake_phase("listening")
    assert app.state == AppState.IDLE
