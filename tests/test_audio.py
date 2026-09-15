"""Audio recorder unit tests — must collect without sounddevice installed."""

from __future__ import annotations

import builtins
import importlib
import sys

import numpy as np
import pytest

from thai_voice_bridge.audio import AudioError, CallbackStop, Recorder, require_sounddevice


def test_audio_and_app_import_without_sounddevice(monkeypatch: pytest.MonkeyPatch) -> None:
    """Safety/wake/app tests must collect even when PortAudio bindings are missing."""
    real_import = builtins.__import__

    def blocked_import(name, globals=None, locals=None, fromlist=(), level=0):  # noqa: ANN001
        if name == "sounddevice" or name.startswith("sounddevice."):
            raise ModuleNotFoundError("No module named 'sounddevice'")
        return real_import(name, globals, locals, fromlist, level)

    for key in list(sys.modules):
        if key == "sounddevice" or key.startswith("sounddevice."):
            monkeypatch.delitem(sys.modules, key, raising=False)
        if key.startswith("thai_voice_bridge.audio") or key.startswith(
            "thai_voice_bridge.wake_listener"
        ) or key.startswith("thai_voice_bridge.app"):
            monkeypatch.delitem(sys.modules, key, raising=False)

    monkeypatch.setattr(builtins, "__import__", blocked_import)

    audio = importlib.import_module("thai_voice_bridge.audio")
    importlib.reload(audio)
    app = importlib.import_module("thai_voice_bridge.app")
    importlib.reload(app)

    assert audio.sd is None
    with pytest.raises(audio.AudioError, match="sounddevice"):
        audio.require_sounddevice()
    with pytest.raises(audio.AudioError, match="sounddevice"):
        audio.Recorder(samplerate=10, max_recording_seconds=1.0).start()


def test_require_sounddevice_fail_closed_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("thai_voice_bridge.audio.sd", None)
    monkeypatch.setattr(
        "thai_voice_bridge.audio._SOUNDDEVICE_IMPORT_ERROR",
        ModuleNotFoundError("No module named 'sounddevice'"),
    )
    with pytest.raises(AudioError, match="sounddevice"):
        require_sounddevice()


def test_require_sounddevice_fail_closed_when_portaudio_query_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BrokenBackend:
        @staticmethod
        def query_devices() -> None:
            raise RuntimeError("PortAudio not initialized")

    monkeypatch.setattr("thai_voice_bridge.audio.sd", BrokenBackend())
    monkeypatch.setattr("thai_voice_bridge.audio._SOUNDDEVICE_IMPORT_ERROR", None)
    with pytest.raises(AudioError, match="PortAudio"):
        require_sounddevice()


def test_recording_limit_bounds_samples_and_rejects_wav():
    recorder = Recorder(samplerate=10, max_recording_seconds=1.0)
    recorder.recording = True

    with pytest.raises(CallbackStop):
        recorder._callback(np.ones((15, 1), dtype=np.float32), 15, None, None)

    assert sum(len(chunk) for chunk in recorder._chunks) == 10
    with pytest.raises(AudioError, match="maximum duration"):
        recorder.stop_to_wav()


class _FakeStream:
    def __init__(self, *, start_exc: Exception | None = None, stop_exc: Exception | None = None, close_exc: Exception | None = None) -> None:
        self.start_exc = start_exc
        self.stop_exc = stop_exc
        self.close_exc = close_exc
        self.started = False
        self.stopped = False
        self.closed = False

    def start(self) -> None:
        if self.start_exc is not None:
            raise self.start_exc
        self.started = True

    def stop(self) -> None:
        if self.stop_exc is not None:
            raise self.stop_exc
        self.stopped = True

    def close(self) -> None:
        if self.close_exc is not None:
            raise self.close_exc
        self.closed = True


def test_recorder_start_rolls_back_stream_when_inputstream_start_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Locally-created InputStream must be closed/cleared if start() raises."""
    stream = _FakeStream(start_exc=RuntimeError("PortAudio start failed"))
    backend = type(
        "Backend",
        (),
        {
            "query_devices": staticmethod(lambda: []),
            "InputStream": staticmethod(lambda **_kwargs: stream),
        },
    )()
    # Patch the defining module globals (may differ from sys.modules after reload tests).
    monkeypatch.setitem(
        Recorder.start.__globals__,
        "require_sounddevice",
        lambda: backend,
    )

    recorder = Recorder(samplerate=10, max_recording_seconds=1.0)
    recorder.microphone = None

    with pytest.raises(RuntimeError, match="PortAudio start failed"):
        recorder.start()

    assert stream.closed is True
    assert recorder._stream is None
    assert recorder.recording is False


def test_recorder_start_close_failure_raises_combined_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stream = _FakeStream(
        start_exc=RuntimeError("PortAudio start failed"),
        close_exc=RuntimeError("close also failed"),
    )
    backend = type(
        "Backend",
        (),
        {
            "query_devices": staticmethod(lambda: []),
            "InputStream": staticmethod(lambda **_kwargs: stream),
        },
    )()
    monkeypatch.setitem(
        Recorder.start.__globals__,
        "require_sounddevice",
        lambda: backend,
    )

    recorder = Recorder(samplerate=10, max_recording_seconds=1.0)
    recorder.microphone = None

    with pytest.raises(AudioError, match=r"start failed:.*cleanup close failed"):
        recorder.start()

    assert recorder._stream is None
    assert recorder.recording is False


def test_recorder_stop_failure_still_closes_and_clears_stream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stream = _FakeStream(stop_exc=RuntimeError("stop blew up"))
    recorder = Recorder(samplerate=10, max_recording_seconds=1.0)
    recorder._stream = stream
    recorder.recording = True

    with pytest.raises(RuntimeError, match="stop blew up"):
        recorder.cancel()

    assert stream.closed is True
    assert recorder._stream is None
    assert recorder.recording is False


def test_recorder_close_failure_still_clears_stream_reference() -> None:
    stream = _FakeStream(close_exc=RuntimeError("close blew up"))
    recorder = Recorder(samplerate=10, max_recording_seconds=1.0)
    recorder._stream = stream
    recorder.recording = True

    with pytest.raises(RuntimeError, match="close blew up"):
        recorder.cancel()

    assert stream.stopped is True
    assert recorder._stream is None
    assert recorder.recording is False
