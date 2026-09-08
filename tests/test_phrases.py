"""Tests for wake/end phrase matching and stripping."""

from __future__ import annotations

import importlib
import inspect

import numpy as np

from thai_voice_bridge.phrases import contains_phrase, strip_command_phrases
from thai_voice_bridge.vad import (
    OFFLINE_SAFE,
    StreamingEnergyVad,
    frame_rms,
    streaming_frame_samples,
)

START = "เฮ้ พุดไทป์"
END = "ส่งได้ พุดไทป์"


def test_detects_start_and_end_phrases():
    assert contains_phrase("เฮ้ พุดไทป์", START, tolerance=0.8)
    assert contains_phrase("ครับ ส่งได้ พุดไทป์", END, tolerance=0.8)
    assert not contains_phrase("พรุ่งนี้ประชุม", END, tolerance=0.8)
    assert not contains_phrase("ส่งได้ พุดไทป์", START, tolerance=0.8)


def test_accepts_common_whisper_aliases_for_brand():
    assert contains_phrase("เฮ้ พุทไทป์", START, tolerance=0.8)
    assert contains_phrase("เฮ พุดไทย", START, tolerance=0.8)
    assert contains_phrase("ส่งได้ พุดไทย", END, tolerance=0.8)


def test_accepts_live_whisper_mishearings_of_wake_phrase():
    # Real transcripts from the user's mic while saying "เฮ้ พุดไทป์".
    assert contains_phrase("โอเค พูดท้าย", START, tolerance=0.75)
    assert contains_phrase("ภูทัย", START, tolerance=0.75)
    assert contains_phrase("เทพุทธ", START, tolerance=0.75)
    assert not contains_phrase("อิสระที่สุดท้าย", START, tolerance=0.75)
    assert not contains_phrase("โอเค", START, tolerance=0.75)


def test_strips_start_and_end_for_paste_payload():
    text = "เฮ้ พุดไทป์ พรุ่งนี้ประชุม 10 โมง ส่งได้ พุดไทป์"
    assert (
        strip_command_phrases(
            text, start_phrase=START, end_phrase=END, tolerance=0.8
        )
        == "พรุ่งนี้ประชุม 10 โมง"
    )


def test_streaming_frame_samples_near_20ms():
    assert streaming_frame_samples(16000) == 320
    assert streaming_frame_samples(16000, frame_ms=30.0) == 480


def test_streaming_vad_is_offline_safe():
    assert OFFLINE_SAFE is True
    vad_mod = importlib.import_module("thai_voice_bridge.vad")
    source = inspect.getsource(vad_mod)
    forbidden = (
        "urllib",
        "requests",
        "http.client",
        "huggingface",
        "torch.hub",
        "wget",
        "socket.create_connection",
    )
    lowered = source.lower()
    for token in forbidden:
        assert token not in lowered


def test_streaming_vad_latency_reduction_closes_sooner_than_configured_hangover():
    """After sustained speech, hangover shrinks so end-phrase ASR can start sooner."""
    samplerate = 16000
    frame = streaming_frame_samples(samplerate)  # 20ms
    speech = np.full(frame, 0.2, dtype=np.float32)
    quiet = np.zeros(frame, dtype=np.float32)

    baseline = StreamingEnergyVad(
        samplerate=samplerate,
        silence_seconds=0.8,
        speech_rms=0.02,
        latency_reduction=False,
        pre_roll_seconds=0.0,
    )
    reduced = StreamingEnergyVad(
        samplerate=samplerate,
        silence_seconds=0.8,
        speech_rms=0.02,
        latency_reduction=True,
        min_silence_seconds=0.25,
        pre_roll_seconds=0.0,
    )

    # ~400ms of speech so adaptive hangover engages.
    for _ in range(20):
        assert baseline.update(speech) == "speech"
        assert reduced.update(speech) == "speech"

    baseline_complete_at = None
    reduced_complete_at = None
    for i in range(50):  # up to 1.0s of silence
        if baseline_complete_at is None and baseline.update(quiet) == "silence_complete":
            baseline_complete_at = (i + 1) * (frame / samplerate)
        if reduced_complete_at is None and reduced.update(quiet) == "silence_complete":
            reduced_complete_at = (i + 1) * (frame / samplerate)

    assert baseline_complete_at is not None
    assert reduced_complete_at is not None
    assert reduced_complete_at < baseline_complete_at
    assert reduced_complete_at <= 0.30


def test_streaming_vad_push_includes_preroll_and_pairs_with_phrase_match():
    samplerate = 16000
    frame = streaming_frame_samples(samplerate)
    quiet = np.zeros(frame, dtype=np.float32)
    speech = np.full(frame, 0.25, dtype=np.float32)

    vad = StreamingEnergyVad(
        samplerate=samplerate,
        silence_seconds=0.1,
        speech_rms=0.02,
        pre_roll_seconds=0.06,
        latency_reduction=False,
    )

    # Warm pre-roll with silence, then speech, then silence hangover.
    for _ in range(5):
        state, utterance = vad.push(quiet)
        assert state == "silence"
        assert utterance is None

    for _ in range(10):
        state, utterance = vad.push(speech)
        assert state == "speech"
        assert utterance is None

    utterance = None
    for _ in range(10):
        state, utterance = vad.push(quiet)
        if state == "silence_complete":
            break
    assert state == "silence_complete"
    assert utterance is not None
    assert utterance.audio.size > 10 * frame  # speech + some pre-roll
    assert frame_rms(utterance.audio) > 0.0
    # Streaming VAD closes the listen window; phrase layer still matches wake text.
    assert contains_phrase("โอเค พูดท้าย", START, tolerance=0.75)
