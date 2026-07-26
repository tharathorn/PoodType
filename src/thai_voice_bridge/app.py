"""Application orchestration: record → transcribe → paste."""

from __future__ import annotations

import threading
from dataclasses import replace
from enum import Enum
from pathlib import Path

import numpy as np

from thai_voice_bridge.audio import Recorder, unique_temp_wav, write_wav
from thai_voice_bridge.config import AppConfig, ConfigError
from thai_voice_bridge.dictionary import is_bad_transcript, normalize_transcript
from thai_voice_bridge.feedback import Feedback
from thai_voice_bridge.foreground import ForegroundInfo, describe_target, get_foreground_info
from thai_voice_bridge.hotkey import HotkeyController
from thai_voice_bridge.paste import PasteError, paste_text
from thai_voice_bridge.phrases import strip_command_phrases
from thai_voice_bridge.privacy import log_transcript, setup_logging, summarize_event
from thai_voice_bridge.wake_listener import WakeWordListener
from thai_voice_bridge.whisper_engine import WhisperEngine, discover_cached_model


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
        self._wake_listener: WakeWordListener | None = None
        self._wake_engine: WhisperEngine | None = None
        self._shutdown = threading.Event()
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

    def start_input(self) -> None:
        """Start the listener for the configured mode (hotkey or wake_word)."""
        self._shutdown.clear()
        if self.config.mode == "wake_word":
            if self._hotkey:
                self._hotkey.disable()
            self._start_wake_listener()
        else:
            self._stop_wake_listener()
            if self._hotkey is None:
                self.start_hotkey()
            else:
                self._hotkey.enable()
                self.logger.info(
                    summarize_event(
                        "ready",
                        mode="hotkey",
                        hotkey=self.config.hotkey,
                        model=self.config.model,
                        device=self.config.device,
                        auto_send=self.config.auto_send,
                    )
                )
        self._set_state(AppState.IDLE)

    def set_mode(self, mode: str) -> None:
        """Switch input mode; cancel in-flight work and restart the active listener."""
        normalized = str(mode).strip().lower()
        if normalized not in {"hotkey", "wake_word"}:
            raise ConfigError("mode must be 'hotkey' or 'wake_word'")

        if self._hotkey:
            self._hotkey.disable()
        self._stop_wake_listener()
        if self.recorder.recording:
            self.recorder.cancel()
        with self._status_lock:
            self._work_generation += 1

        self.config.mode = normalized
        self.start_input()

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
                mode="hotkey",
                hotkey=self.config.hotkey,
                model=self.config.model,
                device=self.config.device,
                auto_send=self.config.auto_send,
            )
        )

    def wait(self) -> None:
        if self.config.mode == "wake_word":
            if self._wake_listener is None:
                raise RuntimeError("Wake listener not started")
            self._shutdown.wait()
            return
        if self._hotkey is None:
            raise RuntimeError("Hotkey not started")
        self._hotkey.wait()

    def stop(self) -> None:
        if self._hotkey:
            self._hotkey.disable()
        self._stop_wake_listener()
        if self.recorder.recording:
            self.recorder.cancel()
        with self._status_lock:
            self._work_generation += 1
        self._shutdown.set()
        self._set_state(AppState.STOPPED)

    def pause_listening(self) -> None:
        if self._hotkey:
            self._hotkey.disable()
        self._stop_wake_listener()
        if self.recorder.recording:
            self.recorder.cancel()
        with self._status_lock:
            self._work_generation += 1
        self._set_state(AppState.STOPPED)

    def resume_listening(self) -> None:
        if self.config.mode == "wake_word":
            self._start_wake_listener()
        elif self._hotkey:
            self._hotkey.enable()
        self._set_state(AppState.IDLE)

    def _start_wake_listener(self) -> None:
        self._stop_wake_listener()
        try:
            self._get_wake_engine().ensure_model()
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("wake_fast_model_preload_failed: %s", exc)
        self._wake_listener = WakeWordListener(
            self.config,
            feedback=self.feedback,
            on_utterance=self._handle_wake_utterance,
            transcribe_window=self._transcribe_window,
            on_phase=self._on_wake_phase,
            open_mic=True,
        )
        self._wake_listener.enable()
        self.logger.info(
            summarize_event(
                "ready",
                mode="wake_word",
                model=self.config.model,
                device=self.config.device,
                start_phrase=self.config.wake_word.start_phrase,
                end_phrase=self.config.wake_word.end_phrase,
            )
        )

    def _stop_wake_listener(self) -> None:
        listener = self._wake_listener
        self._wake_listener = None
        if listener is not None:
            listener.disable()

    def _on_wake_phase(self, phase: str) -> None:
        if phase == "recording":
            with self._status_lock:
                if self.state in (AppState.STOPPED, AppState.BUSY):
                    return
            self._set_state(AppState.RECORDING)
            return
        if phase == "listening":
            with self._status_lock:
                if self.state != AppState.RECORDING:
                    return
            self._set_state(AppState.IDLE)

    def _get_wake_engine(self) -> WhisperEngine:
        """Faster/smaller model for wake/end phrase windows (not final paste)."""
        if self._wake_engine is not None:
            return self._wake_engine
        wake_model = "small"
        if discover_cached_model(wake_model, self.config.hf_cache_dir) is None:
            wake_model = self.config.model
            self.logger.info("wake_fast_model_missing fallback=%s", wake_model)
        wake_cfg = replace(
            self.config,
            model=wake_model,
            beam_size=1,
            initial_prompt=(
                f"{self.config.wake_word.start_phrase} "
                f"{self.config.wake_word.end_phrase}"
            ),
        )
        self._wake_engine = WhisperEngine(wake_cfg)
        self.logger.info("wake_fast_model=%s beam_size=1", wake_model)
        return self._wake_engine

    def _transcribe_window(self, audio: np.ndarray) -> str:
        samples = np.asarray(audio, dtype=np.float32).reshape(-1)
        # Keep the end of the utterance — wake/end phrases are spoken last.
        max_samples = max(1, int(self.config.samplerate * 2.5))
        if samples.size > max_samples:
            samples = samples[-max_samples:]
        path = unique_temp_wav(prefix="poodtype_wake_win_")
        try:
            write_wav(path, samples, self.config.samplerate)
            result = self._get_wake_engine().transcribe_file(path)
            return (result.text or "").strip()
        finally:
            if not self.config.privacy.persist_audio:
                try:
                    path.unlink(missing_ok=True)
                except OSError as exc:
                    self.logger.warning("wake_window_wav_cleanup_failed: %s", exc)

    def _handle_wake_utterance(self, wav_path: Path) -> None:
        expected_foreground = get_foreground_info()
        with self._status_lock:
            if self.state == AppState.STOPPED:
                self._cleanup_wav(wav_path)
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
            kwargs={
                "wav_path": wav_path,
                "strip_wake_phrases": True,
                "auto_send": False,
            },
            daemon=True,
        ).start()

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
        *,
        wav_path: Path | None = None,
        strip_wake_phrases: bool = False,
        auto_send: bool | None = None,
    ) -> None:
        if work_generation is None:
            with self._status_lock:
                work_generation = self._work_generation
        send = self.config.auto_send if auto_send is None else auto_send
        try:
            if wav_path is None:
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
            if strip_wake_phrases:
                text = strip_command_phrases(
                    text,
                    start_phrase=self.config.wake_word.start_phrase,
                    end_phrase=self.config.wake_word.end_phrase,
                    tolerance=self.config.wake_word.match_tolerance,
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
                    auto_send=send,
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
                paste_text(text, auto_send=send)
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
