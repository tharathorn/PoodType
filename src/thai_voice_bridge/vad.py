"""Lightweight RMS energy VAD for wake-word listening."""

from __future__ import annotations

from typing import Literal

import numpy as np

VadState = Literal["speech", "silence", "silence_complete"]


class EnergyVad:
    def __init__(
        self,
        *,
        samplerate: int,
        silence_seconds: float,
        speech_rms: float = 0.02,
    ) -> None:
        if samplerate <= 0:
            raise ValueError("samplerate must be positive")
        if silence_seconds <= 0:
            raise ValueError("silence_seconds must be positive")
        self.samplerate = samplerate
        self.silence_seconds = silence_seconds
        self.speech_rms = speech_rms
        self._heard_speech = False
        self._silent_samples = 0

    def reset(self) -> None:
        self._heard_speech = False
        self._silent_samples = 0

    def update(self, frame: np.ndarray) -> VadState:
        samples = np.asarray(frame, dtype=np.float32).reshape(-1)
        if samples.size == 0:
            return "silence"
        rms = float(np.sqrt(np.mean(np.square(samples))))
        if rms >= self.speech_rms:
            self._heard_speech = True
            self._silent_samples = 0
            return "speech"

        if not self._heard_speech:
            return "silence"

        self._silent_samples += int(samples.size)
        if self._silent_samples / self.samplerate >= self.silence_seconds:
            self.reset()
            return "silence_complete"
        return "silence"
