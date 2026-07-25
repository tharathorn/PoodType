from pathlib import Path
from unittest.mock import MagicMock, patch

from thai_voice_bridge.app import AppState, VoiceBridgeApp
from thai_voice_bridge.config import config_from_dict
from thai_voice_bridge.foreground import ForegroundInfo
from thai_voice_bridge.whisper_engine import TranscriptResult


def _app() -> VoiceBridgeApp:
    return VoiceBridgeApp(
        config_from_dict(
            {
                "language": "th",
                "task": "transcribe",
                "feedback": {"enabled": False},
            }
        )
    )


def _target(hwnd: int) -> ForegroundInfo:
    return ForegroundInfo(
        hwnd=hwnd,
        process_name="Cursor.exe",
        process_id=42,
        window_title="Cursor",
    )


def _successful_pipeline(app: VoiceBridgeApp, tmp_path: Path) -> None:
    wav = tmp_path / "speech.wav"
    wav.write_bytes(b"RIFF")
    app.recorder.stop_to_wav = MagicMock(return_value=wav)  # type: ignore[method-assign]
    app.engine.transcribe_file = MagicMock(  # type: ignore[method-assign]
        return_value=TranscriptResult(
            text="ทดสอบ",
            language="th",
            language_probability=1.0,
            avg_confidence=0.9,
            used_vad=True,
        )
    )


def test_pause_cancels_active_recording():
    app = _app()
    app.recorder.recording = True
    app.recorder.cancel = MagicMock()  # type: ignore[method-assign]

    app.pause_listening()

    app.recorder.cancel.assert_called_once()
    assert app.state == AppState.STOPPED


def test_stop_cancels_active_recording():
    app = _app()
    app.recorder.recording = True
    app.recorder.cancel = MagicMock()  # type: ignore[method-assign]

    app.stop()

    app.recorder.cancel.assert_called_once()
    assert app.state == AppState.STOPPED


def test_stop_invalidates_inflight_transcription_before_paste(tmp_path: Path):
    app = _app()
    _successful_pipeline(app, tmp_path)
    generation = app._work_generation
    app.engine.transcribe_file.side_effect = lambda _path: (  # type: ignore[attr-defined]
        app.stop()
        or TranscriptResult("ทดสอบ", "th", 1.0, 0.9, True)
    )

    with patch("thai_voice_bridge.app.get_foreground_info", return_value=_target(1)), patch(
        "thai_voice_bridge.app.paste_text"
    ) as paste:
        app._transcribe_and_paste(_target(1), generation)

    paste.assert_not_called()
    assert app.state == AppState.STOPPED


def test_changed_foreground_aborts_paste(tmp_path: Path):
    app = _app()
    _successful_pipeline(app, tmp_path)

    with patch("thai_voice_bridge.app.get_foreground_info", return_value=_target(2)), patch(
        "thai_voice_bridge.app.paste_text"
    ) as paste:
        app._transcribe_and_paste(_target(1), app._work_generation)

    paste.assert_not_called()


def test_unknown_foreground_aborts_paste(tmp_path: Path):
    app = _app()
    _successful_pipeline(app, tmp_path)

    with patch("thai_voice_bridge.app.get_foreground_info", return_value=None), patch(
        "thai_voice_bridge.app.paste_text"
    ) as paste:
        app._transcribe_and_paste(None, app._work_generation)

    paste.assert_not_called()
