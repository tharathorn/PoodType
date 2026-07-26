"""Hands-free wake-word listening loop (VAD + short Whisper windows)."""

from __future__ import annotations

import logging
import queue
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Literal

import numpy as np
import sounddevice as sd

from thai_voice_bridge.audio import (
    resolve_input_device,
    unique_temp_wav,
    write_wav,
)
from thai_voice_bridge.config import AppConfig
from thai_voice_bridge.feedback import Feedback
from thai_voice_bridge.phrases import contains_phrase
from thai_voice_bridge.vad import EnergyVad

logger = logging.getLogger("thai_voice_bridge.wake")


def _concat_audio(chunks: list[np.ndarray]) -> np.ndarray:
    """Join float32 frames without peak-normalization.

    Peak-normalizing quiet room noise makes Faster Whisper hallucinate
    (e.g. repeating สวัสดี / ต่อไป), which breaks wake-phrase matching.
    """
    if not chunks:
        return np.array([], dtype=np.float32)
    return np.concatenate(chunks, axis=0).astype(np.float32)


def _is_looping_hallucination(text: str) -> bool:
    tokens = [t for t in (text or "").split() if t]
    if len(tokens) >= 6 and len(set(tokens)) <= 2:
        return True
    compact = (text or "").replace(" ", "")
    if len(compact) < 24:
        return False
    # Repeated 4–12 char substrings (common Whisper loop on noise).
    for size in (4, 6, 8, 12):
        if len(compact) < size * 3:
            continue
        chunk = compact[:size]
        if compact.count(chunk) >= 4:
            return True
    return False


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
            speech_rms=config.wake_word.speech_rms,
        )
        self._speech_chunks: list[np.ndarray] = []
        self._record_chunks: list[np.ndarray] = []
        self._record_samples = 0
        self._max_samples = max(1, int(config.samplerate * config.max_recording_seconds))
        self._device = resolve_input_device(config.microphone)
        # Whisper must NOT run on the PortAudio callback thread — it blocks the mic.
        self._asr_queue: queue.Queue[AsrJob | None] = queue.Queue()
        self._asr_busy = False
        self._pending_job: AsrJob | None = None
        self._worker_stop = threading.Event()
        self._worker: threading.Thread | None = None
        self._callback_frames = 0
        self._peak_rms = 0.0
        self._last_audio_log = 0.0
        self._speech_logged = False

    def enable(self) -> None:
        with self._lock:
            self._enabled = True
            self.phase = "listening"
            self._reset_buffers()
        self._speech_logged = False
        self._callback_frames = 0
        self._peak_rms = 0.0
        self._last_audio_log = 0.0
        self._ensure_worker()
        if self.open_mic:
            self.start()
        logger.info(
            "wake_listener_enabled open_mic=%s speech_rms=%.5f silence=%.2fs",
            self.open_mic,
            self.config.wake_word.speech_rms,
            self.config.wake_word.vad_silence_seconds,
        )

    def disable(self) -> None:
        with self._lock:
            self._enabled = False
            self.phase = "listening"
            self._reset_buffers()
        self.stop()
        self._stop_worker()

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
        logger.info("wake_mic_started device=%s", self._device)

    def stop(self) -> None:
        if self._stream is None:
            return
        try:
            self._stream.stop()
        finally:
            self._stream.close()
            self._stream = None

    def wait_asr_idle(self, timeout: float = 2.0) -> bool:
        """Block until ASR queue is drained (for tests)."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._asr_queue.empty() and not self._asr_busy:
                return True
            time.sleep(0.01)
        return False

    def _ensure_worker(self) -> None:
        if self._worker is not None and self._worker.is_alive():
            return
        self._worker_stop.clear()
        self._worker = threading.Thread(
            target=self._asr_loop,
            name="poodtype-wake-asr",
            daemon=True,
        )
        self._worker.start()

    def _stop_worker(self) -> None:
        self._worker_stop.set()
        try:
            self._asr_queue.put_nowait(None)
        except queue.Full:
            pass
        worker = self._worker
        self._worker = None
        if worker is not None and worker.is_alive():
            worker.join(timeout=2.0)
        # Drop any leftover jobs
        while True:
            try:
                self._asr_queue.get_nowait()
            except queue.Empty:
                break
        self._asr_busy = False
        self._pending_job = None

    def _asr_loop(self) -> None:
        while not self._worker_stop.is_set():
            try:
                job = self._asr_queue.get(timeout=0.2)
            except queue.Empty:
                continue
            if job is None:
                break
            kind, audio = job
            self._asr_busy = True
            try:
                if kind == "listen":
                    self._handle_listen_job(audio)
                else:
                    self._handle_end_job(audio)
            except Exception as exc:  # noqa: BLE001
                logger.exception("wake_asr_job_failed kind=%s: %s", kind, exc)
            finally:
                self._asr_busy = False
                pending = self._pending_job
                self._pending_job = None
                if pending is not None and not self._worker_stop.is_set():
                    try:
                        self._asr_queue.put_nowait(pending)
                    except queue.Full:
                        self._pending_job = pending

    def _handle_listen_job(self, audio: np.ndarray) -> None:
        with self._lock:
            if not self._enabled or self.phase != "listening":
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
                if not self._enabled or self.phase != "listening":
                    return
                self.phase = "recording"
                self._record_chunks = []
                self._record_samples = 0
                self._speech_chunks = []
                self._vad.reset()
            self._notify_phase("recording")
            self.feedback.start()
            logger.info("wake_start_phrase_matched")
            return
        # Ignore looping Whisper hallucinations (ambient → repeated filler).
        if _is_looping_hallucination(text):
            logger.info("wake_listen_hallucination_ignored")
            return

    def _handle_end_job(self, audio: np.ndarray) -> None:
        with self._lock:
            if not self._enabled or self.phase != "recording":
                return
        try:
            text = self.transcribe_window(audio)
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

    def _enqueue_asr(self, kind: Literal["listen", "end"], audio: np.ndarray) -> None:
        if audio.size == 0:
            return
        peak = float(np.max(np.abs(audio))) if audio.size else 0.0
        # Ambient ticks (~0.003) flood the ASR queue and stall wake detection.
        # Clear speech for the wake phrase typically peaks >= ~0.02.
        min_peak = max(self.config.wake_word.speech_rms * 1.5, 0.015)
        if peak < min_peak:
            logger.info(
                "wake_asr_skip_quiet kind=%s peak=%.5f min=%.5f",
                kind,
                peak,
                min_peak,
            )
            return
        job: AsrJob = (kind, audio)
        # If ASR is busy, keep only the newest/loudest window.
        if self._asr_busy or not self._asr_queue.empty():
            pending = self._pending_job
            if pending is not None:
                prev_peak = float(np.max(np.abs(pending[1]))) if pending[1].size else 0.0
                if peak < prev_peak * 0.7:
                    logger.info(
                        "wake_asr_drop_softer kind=%s peak=%.5f kept=%.5f",
                        kind,
                        peak,
                        prev_peak,
                    )
                    return
            self._pending_job = job
            logger.info(
                "wake_asr_pending kind=%s peak=%.5f samples=%d",
                kind,
                peak,
                int(audio.size),
            )
            return
        self._asr_queue.put(job)

    def feed_audio(self, frame: np.ndarray) -> None:
        samples = np.asarray(frame, dtype=np.float32).reshape(-1)
        if samples.size == 0:
            return
        rms = float(np.sqrt(np.mean(np.square(samples))))
        self._callback_frames += 1
        if rms > self._peak_rms:
            self._peak_rms = rms
        now = time.monotonic()
        if now - self._last_audio_log >= 2.0:
            logger.info(
                "wake_audio_tick phase=%s frames=%d peak_rms=%.5f threshold=%.5f",
                self.phase,
                self._callback_frames,
                self._peak_rms,
                self.config.wake_word.speech_rms,
            )
            self._peak_rms = 0.0
            self._callback_frames = 0
            self._last_audio_log = now
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
            if not self._speech_logged:
                logger.info("wake_speech_detected")
                self._speech_logged = True
            self._speech_chunks.append(samples.copy())
            # The wake phrase is short (~1.5s). Cap the listening buffer so long
            # talking doesn't build a huge window that Whisper loops on.
            listen_cap = int(self.config.samplerate * 4.0)
            total = sum(int(c.size) for c in self._speech_chunks)
            if total > listen_cap:
                window = _concat_audio(self._speech_chunks)[-listen_cap:]
                self._speech_chunks = []
                self._vad.reset()
                self._speech_logged = False
                self._enqueue_asr("listen", window)
            return
        if state != "silence_complete":
            if state == "silence" and self._speech_chunks:
                self._speech_chunks.append(samples.copy())
            return

        self._speech_logged = False
        audio = _concat_audio(self._speech_chunks)
        self._speech_chunks = []
        # Ignore clicks / blips shorter than ~0.5s (wake phrase is ~1–1.5s).
        if audio.size < int(self.config.samplerate * 0.5):
            logger.info("wake_window_too_short samples=%d", int(audio.size))
            return
        logger.info("wake_silence_complete samples=%d", int(audio.size))
        self._enqueue_asr("listen", audio)

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

        window = _concat_audio(self._speech_chunks)
        self._speech_chunks = []
        if window.size < int(self.config.samplerate * 0.25):
            return
        self._enqueue_asr("end", window)

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
        audio = _concat_audio(chunks)
        if audio.size == 0:
            self._notify_phase("listening")
            self.feedback.error()
            return
        # Peak-normalize only the final utterance for the paste model.
        peak = float(np.max(np.abs(audio))) if audio.size else 0.0
        if peak > 0:
            audio = audio / peak
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
