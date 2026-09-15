"""Microphone capture to unique temporary WAV files."""

from __future__ import annotations

import tempfile
import threading
import uuid
import wave
from pathlib import Path
from typing import Any

import numpy as np

try:
    import sounddevice as sd
except Exception as exc:  # noqa: BLE001 — missing package or PortAudio backend
    sd = None
    _SOUNDDEVICE_IMPORT_ERROR: BaseException | None = exc
else:
    _SOUNDDEVICE_IMPORT_ERROR = None


class AudioError(RuntimeError):
    pass


class _FallbackCallbackStop(Exception):
    """Used when sounddevice is unavailable; mirrors PortAudio CallbackStop."""


CallbackStop: type[BaseException]
if sd is not None:
    CallbackStop = sd.CallbackStop
else:
    CallbackStop = _FallbackCallbackStop


def require_sounddevice() -> Any:
    """Return a ready sounddevice module, or fail closed with a clear dependency error.

    Import success alone is not readiness — PortAudio must answer query_devices.
    """
    if sd is None:
        detail = (
            f" ({_SOUNDDEVICE_IMPORT_ERROR})"
            if _SOUNDDEVICE_IMPORT_ERROR is not None
            else ""
        )
        raise AudioError(
            "Audio recording requires the 'sounddevice' package with a working "
            "PortAudio backend. Install project dependencies from requirements.txt"
            f"{detail}."
        ) from _SOUNDDEVICE_IMPORT_ERROR
    try:
        sd.query_devices()
    except Exception as exc:  # noqa: BLE001 — any PortAudio failure is fail-closed
        raise AudioError(
            "Audio recording requires a working PortAudio backend "
            f"(sounddevice.query_devices failed: {exc})."
        ) from exc
    return sd


def list_input_devices() -> list[tuple[int, str]]:
    backend = require_sounddevice()
    devices: list[tuple[int, str]] = []
    for index, device in enumerate(backend.query_devices()):
        if int(device.get("max_input_channels") or 0) > 0:
            devices.append((index, str(device.get("name") or f"device-{index}")))
    return devices


def resolve_input_device(microphone: int | str | None) -> int | str | None:
    if microphone is None or microphone == "":
        return None
    if isinstance(microphone, int):
        return microphone
    text = str(microphone).strip()
    if text.isdigit():
        return int(text)
    # Name substring match
    needle = text.lower()
    for index, name in list_input_devices():
        if needle in name.lower():
            return index
    raise AudioError(f"Microphone not found: {microphone!r}")


def normalize_audio(chunks: list[np.ndarray]) -> np.ndarray:
    if not chunks:
        return np.array([], dtype=np.float32)
    audio = np.concatenate(chunks, axis=0).astype(np.float32)
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    if peak > 0:
        audio /= peak
    return audio


def write_wav(path: Path, audio: np.ndarray, samplerate: int) -> None:
    pcm = np.clip(audio * 32767.0, -32768, 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(samplerate)
        wav_file.writeframes(pcm.tobytes())


def unique_temp_wav(prefix: str = "tvb_") -> Path:
    name = f"{prefix}{uuid.uuid4().hex}.wav"
    return Path(tempfile.gettempdir()) / name


class Recorder:
    def __init__(
        self,
        *,
        samplerate: int = 16000,
        microphone: int | str | None = None,
        max_recording_seconds: float = 300.0,
    ) -> None:
        self.samplerate = samplerate
        self.microphone = resolve_input_device(microphone)
        self.max_recording_seconds = max_recording_seconds
        self._max_samples = max(1, int(samplerate * max_recording_seconds))
        self._stream: Any = None
        self._chunks: list[np.ndarray] = []
        self._sample_count = 0
        self._limit_exceeded = False
        self._lock = threading.Lock()
        self.recording = False

    def _callback(self, indata, frames, time_info, status) -> None:  # noqa: ANN001
        del frames, time_info, status
        chunk = indata.copy().reshape(-1)
        exceeded = False
        with self._lock:
            remaining = self._max_samples - self._sample_count
            if remaining > 0:
                kept = chunk[:remaining]
                self._chunks.append(kept)
                self._sample_count += len(kept)
            if len(chunk) > remaining:
                self._limit_exceeded = True
                exceeded = True
        if exceeded:
            raise CallbackStop

    def start(self) -> None:
        if self.recording:
            raise AudioError("Already recording")
        backend = require_sounddevice()
        with self._lock:
            self._chunks = []
            self._sample_count = 0
            self._limit_exceeded = False
        stream = backend.InputStream(
            samplerate=self.samplerate,
            channels=1,
            dtype="float32",
            callback=self._callback,
            device=self.microphone,
        )
        try:
            stream.start()
        except Exception as start_exc:
            # Locally-created stream must not leak if start() fails.
            close_exc: BaseException | None = None
            try:
                stream.close()
            except BaseException as exc:  # noqa: BLE001 — preserve cleared state
                close_exc = exc
            self._stream = None
            self.recording = False
            if close_exc is not None:
                raise AudioError(
                    f"InputStream.start failed: {start_exc}; "
                    f"cleanup close failed: {close_exc}"
                ) from start_exc
            raise
        self._stream = stream
        self.recording = True

    def cancel(self) -> None:
        close_error: BaseException | None = None
        try:
            self._close_stream()
        except BaseException as exc:  # noqa: BLE001 — clear state even on failure
            close_error = exc
        with self._lock:
            self._chunks = []
            self._sample_count = 0
            self._limit_exceeded = False
        self.recording = False
        if close_error is not None:
            raise close_error

    def stop_to_wav(self, *, persist: bool = False) -> Path | None:
        """Stop recording and write a unique WAV. Returns None if empty."""
        close_error: BaseException | None = None
        try:
            self._close_stream()
        except BaseException as exc:  # noqa: BLE001 — clear recording even on failure
            close_error = exc
        self.recording = False
        with self._lock:
            chunks = list(self._chunks)
            limit_exceeded = self._limit_exceeded
            self._chunks = []
            self._sample_count = 0
            self._limit_exceeded = False
        if close_error is not None:
            raise close_error
        if limit_exceeded:
            raise AudioError(
                f"Recording exceeded maximum duration of "
                f"{self.max_recording_seconds:g} seconds"
            )
        audio = normalize_audio(chunks)
        if audio.size == 0:
            return None
        path = unique_temp_wav()
        write_wav(path, audio, self.samplerate)
        if persist:
            # Caller opted into persistence — leave file; otherwise caller deletes.
            pass
        return path

    def _close_stream(self) -> None:
        if self._stream is None:
            return
        stream = self._stream
        errors: list[BaseException] = []
        try:
            stream.stop()
        except BaseException as exc:  # noqa: BLE001 — still attempt close/clear
            errors.append(exc)
        try:
            stream.close()
        except BaseException as exc:  # noqa: BLE001 — still clear reference
            errors.append(exc)
        finally:
            self._stream = None
        if errors:
            raise errors[0]
