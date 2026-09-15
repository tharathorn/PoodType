"""Tests for WakeWordListener state machine with faked ASR."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from thai_voice_bridge.config import config_from_dict
from thai_voice_bridge.wake_listener import WakeWordListener


class ScriptedASR:
    def __init__(self, replies: list[str]) -> None:
        self.replies = list(replies)
        self.calls = 0

    def __call__(self, audio: np.ndarray) -> str:
        del audio
        if not self.replies:
            return ""
        self.calls += 1
        return self.replies.pop(0)


def _speech_frame(samples: int = 1600, level: float = 0.2) -> np.ndarray:
    return np.full(samples, level, dtype=np.float32)


def _quiet_frame(samples: int = 1600) -> np.ndarray:
    return np.zeros(samples, dtype=np.float32)


def _pump_utterance(
    listener: WakeWordListener,
    *,
    frames: int = 8,
    quiet_frames: int = 2,
) -> None:
    for _ in range(frames):
        listener.feed_audio(_speech_frame())
    for _ in range(quiet_frames):
        listener.feed_audio(_quiet_frame())


def test_start_phrase_enters_recording_and_end_phrase_emits_utterance(tmp_path: Path):
    del tmp_path
    cfg = config_from_dict(
        {
            "mode": "wake_word",
            "max_recording_seconds": 300,
            "wake_word": {"vad_silence_seconds": 0.1},
        }
    )
    feedback = MagicMock()
    utterances: list[Path] = []
    asr = ScriptedASR(
        [
            "เฮ้ พุดไทป์",
            "พรุ่งนี้ประชุม 10 โมง ส่งได้ พุดไทป์",
        ]
    )
    phases: list[str] = []
    listener = WakeWordListener(
        cfg,
        feedback=feedback,
        on_utterance=lambda path: utterances.append(path),
        transcribe_window=asr,
        on_phase=phases.append,
        open_mic=False,
    )
    listener.enable()

    _pump_utterance(listener)
    assert listener.wait_asr_idle(timeout=2.0)
    assert listener.phase == "recording"
    feedback.start.assert_called_once()
    assert phases == ["recording"]

    _pump_utterance(listener)
    assert listener.wait_asr_idle(timeout=2.0)
    assert listener.phase == "listening"
    feedback.stop.assert_called_once()
    # Finish path leaves tray red until app flips to BUSY (no listening notify).
    assert phases == ["recording"]
    assert len(utterances) == 1
    assert utterances[0].exists()
    utterances[0].unlink(missing_ok=True)
    listener.disable()


def test_end_phrase_ignored_while_listening():
    cfg = config_from_dict(
        {
            "mode": "wake_word",
            "wake_word": {"vad_silence_seconds": 0.1},
        }
    )
    feedback = MagicMock()
    utterances: list[Path] = []
    asr = ScriptedASR(["ส่งได้ พุดไทป์"])
    listener = WakeWordListener(
        cfg,
        feedback=feedback,
        on_utterance=lambda path: utterances.append(path),
        transcribe_window=asr,
        open_mic=False,
    )
    listener.enable()
    _pump_utterance(listener)
    assert listener.wait_asr_idle(timeout=2.0)
    assert listener.phase == "listening"
    assert utterances == []
    feedback.start.assert_not_called()
    feedback.stop.assert_not_called()
    listener.disable()


def test_max_duration_discards_without_utterance_callback():
    cfg = config_from_dict(
        {
            "mode": "wake_word",
            "max_recording_seconds": 0.25,
            "wake_word": {"vad_silence_seconds": 0.1},
        }
    )
    feedback = MagicMock()
    utterances: list[Path] = []
    asr = ScriptedASR(["เฮ้ พุดไทป์", "should not matter"])
    listener = WakeWordListener(
        cfg,
        feedback=feedback,
        on_utterance=lambda path: utterances.append(path),
        transcribe_window=asr,
        open_mic=False,
    )
    listener.enable()
    _pump_utterance(listener, frames=8, quiet_frames=2)
    assert listener.wait_asr_idle(timeout=2.0)
    assert listener.phase == "recording"
    # Exceed 0.25s at 16kHz (~4000 samples) with several frames.
    for _ in range(5):
        listener.feed_audio(_speech_frame(1600))
    assert listener.phase == "listening"
    assert utterances == []
    feedback.error.assert_called()
    listener.disable()


def test_enable_rolls_back_worker_when_mic_start_fails():
    """Failed open_mic must not leak ASR thread / enabled state."""
    cfg = config_from_dict(
        {
            "mode": "wake_word",
            "wake_word": {"vad_silence_seconds": 0.1},
        }
    )
    listener = WakeWordListener(
        cfg,
        feedback=MagicMock(),
        on_utterance=lambda _path: None,
        transcribe_window=lambda _audio: "",
        open_mic=True,
    )
    with patch(
        "thai_voice_bridge.wake_listener.require_sounddevice",
        return_value=MagicMock(),
    ), patch.object(listener, "start", side_effect=RuntimeError("InputStream failed")):
        with pytest.raises(RuntimeError, match="InputStream"):
            listener.enable()

    assert listener._enabled is False
    assert listener._stream is None
    assert listener._worker is None
    assert listener._asr_queue.empty()


def _listener(**kwargs) -> WakeWordListener:
    cfg = config_from_dict(
        {
            "mode": "wake_word",
            "wake_word": {"vad_silence_seconds": 0.1},
        }
    )
    defaults = dict(
        feedback=MagicMock(),
        on_utterance=lambda _path: None,
        transcribe_window=lambda _audio: "",
        open_mic=False,
    )
    defaults.update(kwargs)
    return WakeWordListener(cfg, **defaults)


def test_blocking_asr_beyond_join_timeout_fails_closed_keeps_worker_ref() -> None:
    """Join timeout must fail closed and retain the worker reference."""
    started = threading.Event()
    release = threading.Event()

    def blocking_asr(audio: np.ndarray) -> str:
        del audio
        started.set()
        release.wait(timeout=5.0)
        return ""

    listener = _listener(transcribe_window=blocking_asr)
    listener.enable()
    listener._enqueue_asr("listen", _speech_frame())
    assert started.wait(timeout=2.0)

    with patch.object(listener, "_join_timeout_seconds", 0.05):
        with pytest.raises(RuntimeError, match="join timed out"):
            listener.disable()

    assert listener._worker is not None
    assert listener._worker.is_alive()
    release.set()
    listener._worker.join(timeout=2.0)
    # Second disable after thread exits should clear cleanly.
    listener.disable()
    assert listener._worker is None


def test_no_asr_callback_effects_after_disable() -> None:
    """Disable must stop phase transitions even if a late ASR result arrives."""
    gate = threading.Event()
    release = threading.Event()
    calls = {"n": 0}

    def slow_asr(audio: np.ndarray) -> str:
        del audio
        calls["n"] += 1
        gate.set()
        release.wait(timeout=5.0)
        return "เฮ้ พุดไทป์"

    feedback = MagicMock()
    phases: list[str] = []
    listener = _listener(
        feedback=feedback,
        transcribe_window=slow_asr,
        on_phase=phases.append,
    )
    listener.enable()
    listener._enqueue_asr("listen", _speech_frame())
    assert gate.wait(timeout=2.0)
    # Soft-disable enabled flag while ASR is mid-flight, then release.
    with listener._lock:
        listener._enabled = False
    release.set()
    assert listener.wait_asr_idle(timeout=2.0)
    assert listener.phase == "listening"
    assert phases == []
    feedback.start.assert_not_called()
    listener.disable()


def test_rapid_reenable_refuses_overlapping_workers_while_old_alive() -> None:
    started = threading.Event()
    release = threading.Event()

    def blocking_asr(audio: np.ndarray) -> str:
        del audio
        started.set()
        release.wait(timeout=5.0)
        return ""

    listener = _listener(transcribe_window=blocking_asr)
    listener.enable()
    first_worker = listener._worker
    first_stop = listener._worker_stop
    listener._enqueue_asr("listen", _speech_frame())
    assert started.wait(timeout=2.0)

    with patch.object(listener, "_join_timeout_seconds", 0.05):
        with pytest.raises(RuntimeError, match="join timed out"):
            listener.disable()

    with pytest.raises(RuntimeError, match="still alive|overlapping"):
        listener.enable()

    assert listener._worker is first_worker
    assert listener._worker_stop is first_stop
    release.set()
    first_worker.join(timeout=2.0)
    listener.disable()


def test_inputstream_start_rolls_back_local_stream() -> None:
    class FakeStream:
        def __init__(self) -> None:
            self.closed = False

        def start(self) -> None:
            raise RuntimeError("InputStream.start failed")

        def stop(self) -> None:
            return None

        def close(self) -> None:
            self.closed = True

    stream = FakeStream()
    backend = MagicMock()
    backend.InputStream.return_value = stream

    listener = _listener(open_mic=True)
    with patch(
        "thai_voice_bridge.wake_listener.require_sounddevice",
        return_value=backend,
    ):
        with pytest.raises(RuntimeError, match="InputStream.start failed"):
            listener.start()

    assert stream.closed is True
    assert listener._stream is None


def test_inputstream_start_close_failure_raises_combined_error() -> None:
    class FakeStream:
        def start(self) -> None:
            raise RuntimeError("InputStream.start failed")

        def close(self) -> None:
            raise RuntimeError("close also failed")

    stream = FakeStream()
    backend = MagicMock()
    backend.InputStream.return_value = stream

    listener = _listener(open_mic=True)
    with patch(
        "thai_voice_bridge.wake_listener.require_sounddevice",
        return_value=backend,
    ):
        with pytest.raises(
            RuntimeError,
            match=r"InputStream.start failed:.*cleanup close failed",
        ):
            listener.start()

    assert listener._stream is None


def test_disable_runs_worker_cleanup_even_if_stream_stop_raises() -> None:
    class BrokenStream:
        def stop(self) -> None:
            raise RuntimeError("stream stop failed")

        def close(self) -> None:
            self.closed = True

    listener = _listener()
    listener.enable()
    worker = listener._worker
    assert worker is not None and worker.is_alive()
    listener._stream = BrokenStream()

    with pytest.raises(RuntimeError, match="stream stop failed"):
        listener.disable()

    assert listener._stream is None
    assert listener._worker is None
    assert not worker.is_alive()


def test_disable_close_failure_still_clears_stream_and_stops_worker() -> None:
    class BrokenClose:
        def stop(self) -> None:
            return None

        def close(self) -> None:
            raise RuntimeError("stream close failed")

    listener = _listener()
    listener.enable()
    worker = listener._worker
    listener._stream = BrokenClose()

    with pytest.raises(RuntimeError, match="stream close failed"):
        listener.disable()

    assert listener._stream is None
    assert listener._worker is None
    assert not worker.is_alive()


def test_worker_stop_uses_per_generation_event() -> None:
    listener = _listener()
    listener.enable()
    first_stop = listener._worker_stop
    first_worker = listener._worker
    listener.disable()
    assert first_stop.is_set()
    assert first_worker is not None
    assert not first_worker.is_alive()

    listener.enable()
    second_stop = listener._worker_stop
    assert second_stop is not first_stop
    assert not second_stop.is_set()
    listener.disable()


def test_join_timeout_then_old_exit_then_enable_processes_new_job() -> None:
    """Stale stop-sentinel must not kill the next worker generation."""
    started = threading.Event()
    release = threading.Event()
    processed: list[str] = []

    def blocking_then_ok(audio: np.ndarray) -> str:
        del audio
        if not started.is_set():
            started.set()
            release.wait(timeout=5.0)
            return ""
        processed.append("ok")
        return "เฮ้ พุดไทป์"

    phases: list[str] = []
    listener = _listener(
        transcribe_window=blocking_then_ok,
        on_phase=phases.append,
    )
    listener.enable()
    old_queue = listener._asr_queue
    listener._enqueue_asr("listen", _speech_frame())
    assert started.wait(timeout=2.0)

    with patch.object(listener, "_join_timeout_seconds", 0.05):
        with pytest.raises(RuntimeError, match="join timed out"):
            listener.disable()

    assert listener._worker is not None
    assert listener._asr_queue is old_queue
    release.set()
    listener._worker.join(timeout=2.0)
    assert not listener._worker.is_alive()

    # Direct enable after old worker exited — must replace queue and process jobs.
    listener.enable()
    new_queue = listener._asr_queue
    assert new_queue is not old_queue
    # Poison left on the abandoned generation queue must not affect the new worker.
    try:
        old_queue.put_nowait(None)
    except Exception:  # noqa: BLE001
        pass

    listener._enqueue_asr("listen", _speech_frame())
    assert listener.wait_asr_idle(timeout=2.0)
    assert processed == ["ok"]
    assert phases == ["recording"]
    assert listener._worker is not None and listener._worker.is_alive()
    listener.disable()


def test_concurrent_enable_creates_exactly_one_worker() -> None:
    listener = _listener()
    barrier = threading.Barrier(2)
    errors: list[BaseException] = []

    def _enable_once() -> None:
        try:
            barrier.wait(timeout=2.0)
            listener.enable()
        except BaseException as exc:  # noqa: BLE001 — collect race failures
            errors.append(exc)

    threads = [
        threading.Thread(target=_enable_once, name="enable-a"),
        threading.Thread(target=_enable_once, name="enable-b"),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5.0)

    assert errors == []
    assert listener._worker is not None
    assert listener._worker.is_alive()
    # Identity: only one Thread object registered after both enable calls.
    worker = listener._worker
    time.sleep(0.05)
    assert listener._worker is worker
    alive = [
        t
        for t in threading.enumerate()
        if t.name == "poodtype-wake-asr" and t.is_alive()
    ]
    assert len(alive) == 1
    listener.disable()
