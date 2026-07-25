"""Application orchestration: record → transcribe → paste."""

from __future__ import annotations

import logging
import threading
from enum import Enum
from pathlib import Path

from thai_voice_bridge.audio import Recorder
from thai_voice_bridge.config import AppConfig
from thai_voice_bridge.dictionary import is_bad_transcript, normalize_transcript
from thai_voice_bridge.feedback import Feedback
from thai_voice_bridge.foreground import ForegroundInfo, describe_target, get_foreground_info
from thai_voice_bridge.hotkey import HotkeyController
from thai_voice_bridge.paste import PasteError, paste_text
from thai_voice_bridge.privacy import log_transcript, setup_logging, summarize_event
from thai_voice_bridge.whisper_engine import WhisperEngine


class AppState(str, Enum):
    IDLE = "idle"
    RECORDING = "recording"
    BUSY = "busy"
    ERROR = "error"
    STOPPED = "stopped"


class VoiceBridgeApp:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.logger = setup_logging(config.privacy)
        self.feedback = Feedback(config.feedback)
        self.engine = WhisperEngine(config)
        self.recorder = Recorder(
            samplerate=config.samplerate,
            microphone=config.microphone,
            max_recording_seconds=config.max_recording_seconds,
        )
        self.state = AppState.IDLE
        self._status_lock = threading.Lock()
        self._work_generation = 0
        self._hotkey: HotkeyController | None = None
        self.on_state_change = None  # optional callable[[AppState], None]

    def _set_state(self, state: AppState) -> None:
        with self._status_lock:
            self.state = state
            callback = self.on_state_change
        if callback:
            try:
                callback(state)
            except Exception:  # noqa: BLE001
                self.logger.exception("state change callback failed")

    def preload_model(self) -> None:
        self.engine.ensure_model()

    def start_hotkey(self) -> None:
        self._hotkey = HotkeyController(
            self.config.hotkey,
            on_press=self._on_press,
            on_release=self._on_release,
            min_hold_seconds=self.config.min_hold_seconds,
        )
        self._hotkey.start()
        self.logger.info(
            summarize_event(
                "ready",
                hotkey=self.config.hotkey,
                model=self.config.model,
                device=self.config.device,
                auto_send=self.config.auto_send,
            )
        )

    def wait(self) -> None:
        if self._hotkey is None:
            raise RuntimeError("Hotkey not started")
        self._hotkey.wait()

    def stop(self) -> None:
        if self._hotkey:
            self._hotkey.disable()
        if self.recorder.recording:
            self.recorder.cancel()
        with self._status_lock:
            self._work_generation += 1
        self._set_state(AppState.STOPPED)

    def pause_listening(self) -> None:
        if self._hotkey:
            self._hotkey.disable()
        if self.recorder.recording:
            self.recorder.cancel()
        with self._status_lock:
            self._work_generation += 1
        self._set_state(AppState.STOPPED)

    def resume_listening(self) -> None:
        if self._hotkey:
            self._hotkey.enable()
        self._set_state(AppState.IDLE)

    def _on_press(self) -> None:
        with self._status_lock:
            if self.state == AppState.BUSY:
                self.feedback.busy()
                return
            if self.state == AppState.RECORDING:
                return
            if self.state == AppState.STOPPED:
                return
        try:
            self.recorder.start()
            self._set_state(AppState.RECORDING)
            self.feedback.start()
            self.logger.info("recording_start")
        except Exception as exc:  # noqa: BLE001
            self.logger.error("recording_failed: %s", exc)
            self.feedback.error()
            self._set_state(AppState.ERROR)
            self._set_state(AppState.IDLE)

    def _on_release(self, held_seconds: float) -> None:
        with self._status_lock:
            if self.state != AppState.RECORDING:
                return
        if held_seconds < self.config.min_hold_seconds:
            self.recorder.cancel()
            self.logger.info("recording_cancelled_too_short held=%.2f", held_seconds)
            self._set_state(AppState.IDLE)
            return
        expected_foreground = get_foreground_info()
        self.feedback.stop()
        with self._status_lock:
            if self.state != AppState.RECORDING:
                return
            self.state = AppState.BUSY
            generation = self._work_generation
            callback = self.on_state_change
        if callback:
            try:
                callback(AppState.BUSY)
            except Exception:  # noqa: BLE001
                self.logger.exception("state change callback failed")
        threading.Thread(
            target=self._transcribe_and_paste,
            args=(expected_foreground, generation),
            daemon=True,
        ).start()

    def _cleanup_wav(self, path: Path | None) -> None:
        if path is None:
            return
        if self.config.privacy.persist_audio:
            return
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            self.logger.warning("temp_wav_cleanup_failed: %s", exc)

    def _transcribe_and_paste(
        self,
        expected_foreground: ForegroundInfo | None = None,
        work_generation: int | None = None,
    ) -> None:
        wav_path: Path | None = None
        if work_generation is None:
            with self._status_lock:
                work_generation = self._work_generation
        try:
            wav_path = self.recorder.stop_to_wav(
                persist=self.config.privacy.persist_audio
            )
            if wav_path is None:
                self.logger.info("no_audio_captured")
                self.feedback.error()
                return

            result = self.engine.transcribe_file(wav_path)
            with self._status_lock:
                if (
                    work_generation != self._work_generation
                    or self.state == AppState.STOPPED
                ):
                    self.logger.info("work_cancelled_before_paste")
                    return

            foreground = get_foreground_info()
            text = normalize_transcript(
                result.text, self.config, foreground=foreground
            )

            if is_bad_transcript(text, initial_prompt=self.config.initial_prompt):
                self.logger.info("empty_or_bad_transcript")
                self.feedback.error()
                return

            if result.avg_confidence < self.config.min_confidence:
                self.logger.info(
                    "confidence_too_low conf=%.2f min=%.2f",
                    result.avg_confidence,
                    self.config.min_confidence,
                )
                self.feedback.error()
                return

            log_transcript(
                self.logger,
                self.config.privacy,
                text,
                confidence=result.avg_confidence,
            )
            self.logger.info(
                summarize_event(
                    "paste_target",
                    target=describe_target(foreground),
                    auto_send=self.config.auto_send,
                )
            )

            if (
                expected_foreground is None
                or foreground is None
                or foreground.hwnd != expected_foreground.hwnd
            ):
                self.logger.info("foreground_changed_paste_aborted")
                self.feedback.error()
                return

            with self._status_lock:
                if (
                    work_generation != self._work_generation
                    or self.state == AppState.STOPPED
                ):
                    self.logger.info("work_cancelled_before_paste")
                    return
                paste_text(text, auto_send=self.config.auto_send)
            self.feedback.success()
        except PasteError as exc:
            self.logger.error("paste_refused: %s", exc)
            self.feedback.error()
        except Exception as exc:  # noqa: BLE001
            self.logger.exception("pipeline_failed: %s", exc)
            self.feedback.error()
        finally:
            self._cleanup_wav(wav_path)
            with self._status_lock:
                should_idle = (
                    work_generation == self._work_generation
                    and self.state != AppState.STOPPED
                )
            if should_idle:
                self._set_state(AppState.IDLE)
