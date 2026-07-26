"""Tests for WakeWordListener state machine with faked ASR."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

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
    frames: int = 2,
    quiet_frames: int = 1,
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
    assert listener.phase == "recording"
    feedback.start.assert_called_once()
    assert phases == ["recording"]

    _pump_utterance(listener)
    assert listener.phase == "listening"
    feedback.stop.assert_called_once()
    # Finish path leaves tray red until app flips to BUSY (no listening notify).
    assert phases == ["recording"]
    assert len(utterances) == 1
    assert utterances[0].exists()
    utterances[0].unlink(missing_ok=True)


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
    assert listener.phase == "listening"
    assert utterances == []
    feedback.start.assert_not_called()
    feedback.stop.assert_not_called()


def test_max_duration_discards_without_utterance_callback():
    cfg = config_from_dict(
        {
            "mode": "wake_word",
            "max_recording_seconds": 0.05,
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
    _pump_utterance(listener, frames=1, quiet_frames=1)
    assert listener.phase == "recording"
    # Feed enough recording audio to exceed 0.05s at 16kHz (~800 samples)
    for _ in range(3):
        listener.feed_audio(_speech_frame(1600))
    assert listener.phase == "listening"
    assert utterances == []
    feedback.error.assert_called()
