"""Tests for wake/end phrase matching and stripping."""

from __future__ import annotations

from thai_voice_bridge.phrases import (
    _END_ALIASES,
    _START_ALIASES,
    _WAKE_MISHEARING_ALIASES,
    _phrase_candidates,
    contains_phrase,
    normalize_phrase_text,
    strip_command_phrases,
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


def test_wake_mishearing_aliases_are_registered_for_start():
    start_candidates = set(_phrase_candidates(START))
    for alias in _WAKE_MISHEARING_ALIASES:
        assert normalize_phrase_text(alias) in start_candidates
        assert normalize_phrase_text(alias) in {
            normalize_phrase_text(item) for item in _START_ALIASES
        }


def test_accepts_live_whisper_mishearings_of_wake_phrase():
    # Real transcripts from the user's mic while saying "เฮ้ พุดไทป์".
    for alias in _WAKE_MISHEARING_ALIASES:
        assert contains_phrase(alias, START, tolerance=0.75), alias
    assert contains_phrase("โอเค พูดท้าย", START, tolerance=0.75)
    assert contains_phrase("ภูทัย", START, tolerance=0.75)
    assert contains_phrase("เทพุทธ", START, tolerance=0.75)
    assert not contains_phrase("อิสระที่สุดท้าย", START, tolerance=0.75)
    assert not contains_phrase("โอเค", START, tolerance=0.75)


def test_wake_mishearings_match_inside_longer_utterances():
    assert contains_phrase("โอเค พูดท้าย พรุ่งนี้ประชุม", START, tolerance=0.75)
    assert contains_phrase("ภูทัย ครับ", START, tolerance=0.75)
    assert contains_phrase("เทพุทธ โน้ตนี้", START, tolerance=0.75)


def test_end_phrase_brand_aliases_do_not_false_positive_as_start():
    # Shared brand mishearings must stay end-only when ส่งได้ is present.
    colliding = (
        "ส่งได้ พูดท้าย",
        "ส่งได้ ภูทัย",
        "ส่งได้ เทพุทธ",
        "ครับ ส่งได้ พูดท้าย",
        "ส่งได้ พุดไทย",
    )
    for text in colliding:
        assert not contains_phrase(text, START, tolerance=0.75), text
        assert contains_phrase(text, END, tolerance=0.75), text


def test_end_aliases_include_wake_brand_mishearings():
    end_candidates = set(_phrase_candidates(END))
    for alias in (
        "ส่งได้ พูดท้าย",
        "ส่งได้ ภูทัย",
        "ส่งได้ เทพุทธ",
    ):
        assert normalize_phrase_text(alias) in end_candidates
        assert normalize_phrase_text(alias) in {
            normalize_phrase_text(item) for item in _END_ALIASES
        }


def test_full_utterance_still_detects_start_when_end_follows():
    text = "เฮ้ พุดไทป์ พรุ่งนี้ประชุม ส่งได้ พุดไทป์"
    assert contains_phrase(text, START, tolerance=0.8)
    assert contains_phrase(text, END, tolerance=0.8)


def test_normalize_phrase_text_collapses_whitespace_and_case():
    assert normalize_phrase_text("  Hey   PoodType  ") == "hey poodtype"
    assert normalize_phrase_text("") == ""
    assert normalize_phrase_text(None) == ""  # type: ignore[arg-type]


def test_strips_start_and_end_for_paste_payload():
    text = "เฮ้ พุดไทป์ พรุ่งนี้ประชุม 10 โมง ส่งได้ พุดไทป์"
    assert (
        strip_command_phrases(
            text, start_phrase=START, end_phrase=END, tolerance=0.8
        )
        == "พรุ่งนี้ประชุม 10 โมง"
    )


def test_strips_wake_mishearing_start_aliases():
    text = "โอเค พูดท้าย พรุ่งนี้ประชุม ส่งได้ พูดท้าย"
    assert (
        strip_command_phrases(
            text, start_phrase=START, end_phrase=END, tolerance=0.75
        )
        == "พรุ่งนี้ประชุม"
    )
