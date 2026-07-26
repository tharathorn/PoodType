"""Tests for energy-based VAD."""

from __future__ import annotations

import numpy as np

from thai_voice_bridge.vad import EnergyVad


def test_silence_complete_after_configured_hangover():
    vad = EnergyVad(samplerate=16000, silence_seconds=0.1, speech_rms=0.02)
    speech = np.full(1600, 0.2, dtype=np.float32)
    quiet = np.zeros(1600, dtype=np.float32)
    assert vad.update(speech) == "speech"
    states = [vad.update(quiet) for _ in range(2)]
    assert "silence_complete" in states
