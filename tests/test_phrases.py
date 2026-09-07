"""Tests for wake/end phrase matching, stripping, and streaming helpers.

Offline only — no microphone, sounddevice, or network imports.
"""

from __future__ import annotations

from thai_voice_bridge.phrases import (
    StreamingPhraseWindow,
    contains_phrase,
    contains_phrase_low_latency,
    normalize_phrase_text,
    normalize_token_stream,
    streaming_text_window,
    strip_command_phrases,
    tokenize_phrase,
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


def test_normalize_token_stream_joins_chunks_and_collapses_stutter():
    assert normalize_token_stream("  เฮ้ ", "พุดไทป์  ") == "เฮ้ พุดไทป์"
    assert normalize_token_stream(["โอเค", "โอเค", "พูดท้าย"]) == "โอเค พูดท้าย"
    assert normalize_token_stream("Hey", "POODTYPE") == "hey poodtype"
    assert normalize_token_stream("", None, "  ") == ""
    assert normalize_phrase_text("  เฮ้   พุดไทป์ ") == "เฮ้ พุดไทป์"


def test_tokenize_phrase_keeps_duplicates():
    assert tokenize_phrase("ไป ไป ตลาด") == ("ไป", "ไป", "ตลาด")
    assert tokenize_phrase("") == ()
    assert tokenize_phrase("  ") == ()


def test_streaming_text_window_keeps_trailing_tokens_and_chars():
    long = "หนึ่ง สอง สาม สี่ ห้า หก เจ็ด แปด เก้า สิบ เฮ้ พุดไทป์"
    window = streaming_text_window(long, max_tokens=4, max_chars=64)
    assert window.endswith("เฮ้ พุดไทป์")
    assert len(window.split()) <= 4

    char_limited = streaming_text_window(
        "aaaaaaaaaaaa bbbbbbbbbbbb เฮ้ พุดไทป์",
        max_tokens=20,
        max_chars=20,
    )
    assert "พุดไทป์" in char_limited
    assert len(char_limited) <= 20


def test_streaming_phrase_window_matches_wake_without_hardware():
    buf = StreamingPhraseWindow(max_tokens=6, max_chars=48)
    assert buf.push("พรุ่งนี้ประชุม") == "พรุ่งนี้ประชุม"
    assert not buf.contains_phrase(START, tolerance=0.8)

    buf.push("โอเค")
    buf.push("โอเค")  # stutter from ASR stream
    assert buf.contains_phrase(START, tolerance=0.75) is False
    buf.push("พูดท้าย")
    assert buf.contains_phrase(START, tolerance=0.75)
    assert buf.text() == "พรุ่งนี้ประชุม โอเค พูดท้าย"
    assert "พูดท้าย" in buf.window()

    buf.clear()
    assert buf.text() == ""
    assert buf.window() == ""


def test_contains_phrase_low_latency_uses_trailing_window_only():
    # Start phrase buried early must not match when the tail window excludes it.
    padded = "เฮ้ พุดไทป์ " + ("คำ " * 40) + "พรุ่งนี้ประชุม"
    assert contains_phrase(padded, START, tolerance=0.8)
    assert not contains_phrase_low_latency(
        padded, START, tolerance=0.8, max_tokens=4, max_chars=32
    )

    # End phrase in the newest ASR tail still matches under the small window.
    trailing = ("คำ " * 40) + "ส่งได้ พุดไทป์"
    assert contains_phrase_low_latency(
        trailing, END, tolerance=0.8, max_tokens=6, max_chars=48
    )


def test_streaming_helpers_import_path_stays_offline():
    import thai_voice_bridge.phrases as phrases_mod

    source = phrases_mod.__file__ or ""
    assert source.endswith("phrases.py")
    # Guardrail: phrase helpers must not pull audio capture stacks.
    forbidden = ("sounddevice", "pyaudio", "numpy", "whisper")
    module_globals = set(phrases_mod.__dict__)
    for name in forbidden:
        assert name not in module_globals
