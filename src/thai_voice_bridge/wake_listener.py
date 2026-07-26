"""Hands-free wake-word listening loop (VAD + short Whisper windows)."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Literal

import numpy as np
import sounddevice as sd

from thai_voice_bridge.audio import (
    normalize_audio,
    resolve_input_device,
    unique_temp_wav,
    write_wav,
)
from thai_voice_bridge.config import AppConfig
from thai_voice_bridge.feedback import Feedback
from thai_voice_bridge.phrases import contains_phrase
from thai_voice_bridge.vad import EnergyVad

logger = logging.getLogger("thai_voice_bridge.wake")

Phase = Literal["listening", "recording"]


class WakeWordListener:
    def __init__(
        self,
        config: AppConfig,
        *,
        feedback: Feedback,
        on_utterance: Callable[[Path], None],
        transcribe_window: Callable[[np.ndarray], str],
        on_phase: Callable[[Phase], None] | None = None,
        open_mic: bool = True,
    ) -> None:
        self.config = config
        self.feedback = feedback
        self.on_utterance = on_utterance
        self.transcribe_window = transcribe_window
        self.on_phase = on_phase
        self.open_mic = open_mic
        self.phase: Phase = "listening"
        self._enabled = False
        self._lock = threading.Lock()
        self._stream: sd.InputStream | None = None
        self._vad = EnergyVad(
            samplerate=config.samplerate,
            silence_seconds=config.wake_word.vad_silence_seconds,
        )
        self._speech_chunks: list[np.ndarray] = []
        self._record_chunks: list[np.ndarray] = []
        self._record_samples = 0
        self._max_samples = max(1, int(config.samplerate * config.max_recording_seconds))
        self._device = resolve_input_device(config.microphone)

    def enable(self) -> None:
        with self._lock:
            self._enabled = True
            self.phase = "listening"
            self._reset_buffers()
        if self.open_mic:
            self.start()

    def disable(self) -> None:
        with self._lock:
            self._enabled = False
            self.phase = "listening"
            self._reset_buffers()
        self.stop()

    def start(self) -> None:
        if not self.open_mic:
            return
        if self._stream is not None:
            return
        self._stream = sd.InputStream(
            samplerate=self.config.samplerate,
            channels=1,
            dtype="float32",
            callback=self._stream_callback,
            device=self._device,
        )
        self._stream.start()

    def stop(self) -> None:
        if self._stream is None:
            return
        try:
            self._stream.stop()
        finally:
            self._stream.close()
            self._stream = None

    def _stream_callback(self, indata, frames, time_info, status) -> None:  # noqa: ANN001
        del frames, time_info, status
        self.feed_audio(indata.copy().reshape(-1))

    def _reset_buffers(self) -> None:
        self._speech_chunks = []
        self._record_chunks = []
        self._record_samples = 0
        self._vad.reset()

    def _notify_phase(self, phase: Phase) -> None:
        callback = self.on_phase
        if callback is None:
            return
        try:
            callback(phase)
        except Exception as exc:  # noqa: BLE001
            logger.exception("on_phase_failed: %s", exc)

    def feed_audio(self, frame: np.ndarray) -> None:
        samples = np.asarray(frame, dtype=np.float32).reshape(-1)
        if samples.size == 0:
            return
        with self._lock:
            if not self._enabled:
                return
            phase = self.phase
        if phase == "listening":
            self._feed_listening(samples)
        else:
            self._feed_recording(samples)

    def _feed_listening(self, samples: np.ndarray) -> None:
        state = self._vad.update(samples)
        if state == "speech":
            self._speech_chunks.append(samples.copy())
            return
        if state != "silence_complete":
            if state == "silence" and self._speech_chunks:
                self._speech_chunks.append(samples.copy())
            return

        audio = normalize_audio(self._speech_chunks)
        self._speech_chunks = []
        if audio.size == 0:
            return
        try:
            text = self.transcribe_window(audio)
        except Exception as exc:  # noqa: BLE001
            logger.error("wake_window_transcribe_failed: %s", exc)
            return
        logger.info("wake_listen_window text=%r", text)
        if contains_phrase(
            text,
            self.config.wake_word.start_phrase,
            tolerance=self.config.wake_word.match_tolerance,
        ):
            with self._lock:
                if not self._enabled:
                    return
                self.phase = "recording"
                self._record_chunks = []
                self._record_samples = 0
            self._notify_phase("recording")
            self.feedback.start()
            logger.info("wake_start_phrase_matched")

    def _feed_recording(self, samples: np.ndarray) -> None:
        exceeded = False
        with self._lock:
            remaining = self._max_samples - self._record_samples
            if remaining <= 0:
                exceeded = True
            else:
                kept = samples[:remaining]
                self._record_chunks.append(kept.copy())
                self._record_samples += int(kept.size)
                if samples.size > remaining:
                    exceeded = True
        if exceeded:
            self._discard_recording_limit()
            return

        state = self._vad.update(samples)
        if state == "speech":
            self._speech_chunks.append(samples.copy())
            return
        if state != "silence_complete":
            if state == "silence" and self._speech_chunks:
                self._speech_chunks.append(samples.copy())
            return

        window = normalize_audio(self._speech_chunks)
        self._speech_chunks = []
        if window.size == 0:
            return
        try:
            text = self.transcribe_window(window)
        except Exception as exc:  # noqa: BLE001
            logger.error("end_window_transcribe_failed: %s", exc)
            return
        logger.info("wake_end_window text=%r", text)
        if contains_phrase(
            text,
            self.config.wake_word.end_phrase,
            tolerance=self.config.wake_word.match_tolerance,
        ):
            self._finish_recording()

    def _discard_recording_limit(self) -> None:
        with self._lock:
            self.phase = "listening"
            self._reset_buffers()
        self._notify_phase("listening")
        self.feedback.error()
        logger.info("wake_recording_limit_exceeded")

    def _finish_recording(self) -> None:
        with self._lock:
            chunks = list(self._record_chunks)
            self.phase = "listening"
            self._reset_buffers()
        # Stay visually "recording" until on_utterance flips app to BUSY.
        self.feedback.stop()
        audio = normalize_audio(chunks)
        if audio.size == 0:
            self._notify_phase("listening")
            self.feedback.error()
            return
        path = unique_temp_wav(prefix="poodtype_wake_")
        write_wav(path, audio, self.config.samplerate)
        try:
            self.on_utterance(path)
        except Exception as exc:  # noqa: BLE001
            logger.exception("on_utterance_failed: %s", exc)
            self._notify_phase("listening")
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
