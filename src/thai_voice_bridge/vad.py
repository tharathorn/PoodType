"""Lightweight streaming RMS energy VAD for wake-word listening.

Offline-safe: pure NumPy, no network, no model downloads, no telemetry.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Literal

import numpy as np

VadState = Literal["speech", "silence", "silence_complete"]

# Documented contract for packaging / safety audits.
OFFLINE_SAFE = True
DEFAULT_STREAM_FRAME_MS = 20.0


def frame_rms(frame: np.ndarray) -> float:
    """Return RMS energy for a mono float frame (empty → 0.0)."""
    samples = np.asarray(frame, dtype=np.float32).reshape(-1)
    if samples.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(samples))))


def streaming_frame_samples(
    samplerate: int, *, frame_ms: float = DEFAULT_STREAM_FRAME_MS
) -> int:
    """Recommended frame length (~20ms) for low-latency streaming VAD."""
    if samplerate <= 0:
        raise ValueError("samplerate must be positive")
    if frame_ms <= 0:
        raise ValueError("frame_ms must be positive")
    return max(1, int(round(samplerate * (frame_ms / 1000.0))))


@dataclass(frozen=True)
class VadUtterance:
    """One speech segment closed by silence hangover (includes optional pre-roll)."""

    audio: np.ndarray
    speech_seconds: float
    silence_seconds_used: float
    end_latency_seconds: float


class EnergyVad:
    """RMS speech / silence detector with optional streaming latency controls.

    Backward-compatible defaults match the original hangover behaviour.
    Enable ``latency_reduction`` and/or ``pre_roll_seconds`` for streaming
    wake windows that close sooner and keep onset samples.
    """

    def __init__(
        self,
        *,
        samplerate: int,
        silence_seconds: float,
        speech_rms: float = 0.02,
        pre_roll_seconds: float = 0.0,
        latency_reduction: bool = False,
        min_silence_seconds: float | None = None,
        speech_confirm_frames: int = 1,
    ) -> None:
        if samplerate <= 0:
            raise ValueError("samplerate must be positive")
        if silence_seconds <= 0:
            raise ValueError("silence_seconds must be positive")
        if pre_roll_seconds < 0:
            raise ValueError("pre_roll_seconds must be >= 0")
        if speech_confirm_frames < 1:
            raise ValueError("speech_confirm_frames must be >= 1")
        if min_silence_seconds is not None and min_silence_seconds <= 0:
            raise ValueError("min_silence_seconds must be positive when set")

        self.samplerate = samplerate
        self.silence_seconds = silence_seconds
        self.speech_rms = speech_rms
        self.pre_roll_seconds = pre_roll_seconds
        self.latency_reduction = latency_reduction
        self.min_silence_seconds = (
            min_silence_seconds
            if min_silence_seconds is not None
            else min(0.25, silence_seconds)
        )
        self.speech_confirm_frames = speech_confirm_frames

        self._heard_speech = False
        self._silent_samples = 0
        self._speech_samples = 0
        self._speech_streak = 0
        self._pre_roll: deque[np.ndarray] = deque()
        self._pre_roll_samples = 0
        self._speech_chunks: list[np.ndarray] = []
        self._trailing_chunks: list[np.ndarray] = []
        self._last_silence_budget = silence_seconds
        self._pending_utterance: VadUtterance | None = None

    @property
    def stream_frame_samples(self) -> int:
        return streaming_frame_samples(self.samplerate)

    @property
    def effective_silence_seconds(self) -> float:
        """Hangover used for the current utterance (may shrink with latency_reduction)."""
        if not self.latency_reduction or not self._heard_speech:
            return self.silence_seconds
        # After ~350ms of sustained speech, tighten hangover to cut end latency.
        if self._speech_samples / self.samplerate < 0.35:
            return self.silence_seconds
        reduced = max(self.min_silence_seconds, self.silence_seconds * 0.35)
        return min(self.silence_seconds, reduced)

    def reset(self) -> None:
        self._heard_speech = False
        self._silent_samples = 0
        self._speech_samples = 0
        self._speech_streak = 0
        self._pre_roll.clear()
        self._pre_roll_samples = 0
        self._speech_chunks = []
        self._trailing_chunks = []
        self._last_silence_budget = self.silence_seconds
        self._pending_utterance = None

    def _push_pre_roll(self, samples: np.ndarray) -> None:
        if self.pre_roll_seconds <= 0:
            return
        self._pre_roll.append(samples.copy())
        self._pre_roll_samples += int(samples.size)
        limit = int(self.samplerate * self.pre_roll_seconds)
        while self._pre_roll_samples > limit and self._pre_roll:
            dropped = self._pre_roll.popleft()
            self._pre_roll_samples -= int(dropped.size)

    def _buffered_audio(self) -> np.ndarray:
        parts: list[np.ndarray] = []
        if self._pre_roll:
            parts.extend(self._pre_roll)
        parts.extend(self._speech_chunks)
        parts.extend(self._trailing_chunks)
        if not parts:
            return np.array([], dtype=np.float32)
        return np.concatenate(parts, axis=0).astype(np.float32)

    def update(self, frame: np.ndarray) -> VadState:
        samples = np.asarray(frame, dtype=np.float32).reshape(-1)
        if samples.size == 0:
            return "silence"

        rms = frame_rms(samples)
        if rms >= self.speech_rms:
            self._speech_streak += 1
            if self._speech_streak < self.speech_confirm_frames and not self._heard_speech:
                # Still idle — keep pre-roll warm but do not latch yet.
                self._push_pre_roll(samples)
                return "silence"

            if not self._heard_speech:
                # Latch speech; pre-roll already holds leading quiet frames.
                self._heard_speech = True
                self._speech_chunks = []
                self._trailing_chunks = []

            self._silent_samples = 0
            self._speech_samples += int(samples.size)
            self._speech_chunks.append(samples.copy())
            self._trailing_chunks = []
            return "speech"

        self._speech_streak = 0
        if not self._heard_speech:
            self._push_pre_roll(samples)
            return "silence"

        self._silent_samples += int(samples.size)
        self._trailing_chunks.append(samples.copy())
        budget = self.effective_silence_seconds
        self._last_silence_budget = budget
        if self._silent_samples / self.samplerate >= budget:
            speech_seconds = (
                sum(int(chunk.size) for chunk in self._speech_chunks) / self.samplerate
                if self._speech_chunks
                else 0.0
            )
            audio = self._buffered_audio()
            self._pending_utterance = (
                VadUtterance(
                    audio=audio,
                    speech_seconds=speech_seconds,
                    silence_seconds_used=float(budget),
                    end_latency_seconds=float(budget),
                )
                if audio.size
                else None
            )
            # Match legacy latch reset while keeping the pending utterance available.
            self._heard_speech = False
            self._silent_samples = 0
            self._speech_samples = 0
            self._speech_streak = 0
            self._pre_roll.clear()
            self._pre_roll_samples = 0
            self._speech_chunks = []
            self._trailing_chunks = []
            return "silence_complete"
        return "silence"

    def take_utterance(self) -> VadUtterance | None:
        """Drain the utterance produced by the latest ``silence_complete``."""
        utterance = self._pending_utterance
        self._pending_utterance = None
        return utterance

    def push(self, frame: np.ndarray) -> tuple[VadState, VadUtterance | None]:
        """Streaming ingest: on ``silence_complete``, also returns the utterance."""
        state = self.update(frame)
        if state == "silence_complete":
            return state, self.take_utterance()
        return state, None


class StreamingEnergyVad(EnergyVad):
    """Energy VAD tuned for ~20ms streaming frames with pre-roll + latency reduction."""

    def __init__(
        self,
        *,
        samplerate: int,
        silence_seconds: float,
        speech_rms: float = 0.02,
        pre_roll_seconds: float = 0.12,
        latency_reduction: bool = True,
        min_silence_seconds: float | None = None,
        speech_confirm_frames: int = 1,
    ) -> None:
        super().__init__(
            samplerate=samplerate,
            silence_seconds=silence_seconds,
            speech_rms=speech_rms,
            pre_roll_seconds=pre_roll_seconds,
            latency_reduction=latency_reduction,
            min_silence_seconds=min_silence_seconds,
            speech_confirm_frames=speech_confirm_frames,
        )
