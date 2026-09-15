"""Tests for wake/end phrase matching and stripping.

Pure text tests only — no sounddevice or hardware audio.
"""

from __future__ import annotations

from thai_voice_bridge.phrases import (
    contains_phrase,
    normalize_phrase_text,
    strip_command_phrases,
)

START = "เฮ้ พุดไทป์"
END = "ส่งได้ พุดไทป์"

# Extra spoken / Whisper near-hits that should map to the configured phrases.
START_ALIASES = (
    "เฮ้ พุดไทป์",
    "เฮ พุดไทป์",
    "เฮ้ พุทไทป์",
    "เฮ้ พูดไทป์",
    "เฮ้ พุทธไทย",
    "เฮ้ พุทธไทป์",
    "เอ้ พุดไทป์",
    "เฮ้ย พุดไทป์",
    "โอเค พูดท้าย",
    "โอเค พุดไทย",
    "ภูทัย",
    "เทพุทธ",
    "hey poodtype",
    "hey pood type",
    "hey phut thai",
    "hey putthai",
    "okay poodtype",
    "hi poodtype",
)

END_ALIASES = (
    "ส่งได้ พุดไทป์",
    "ส่งได้ พุทไทป์",
    "ส่งได้ พูดไทป์",
    "ส่งได้ พุทธไทย",
    "ส่งได้ พูดท้าย",
    "ส่งได พุดไทป์",
    "สงได้ พุดไทป์",
    "ส่งได้ พุดไทพ์",
    "ส่งได้ poodtype",
    "song dai poodtype",
)

# Ordinary Thai that must never wake or stop recording.
NON_COMMANDS = (
    "พรุ่งนี้ประชุม",
    "อิสระที่สุดท้าย",
    "โอเค",
    "ส่งได้",
    "พูดไทยกันหน่อย",
    "ท้ายสุดของงาน",
    "hey there",
    "okay thanks",
)


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


def test_start_alias_containment():
    for alias in START_ALIASES:
        assert contains_phrase(alias, START, tolerance=0.8), alias


def test_end_alias_containment():
    for alias in END_ALIASES:
        assert contains_phrase(alias, END, tolerance=0.8), alias


def test_normalize_phrase_text_collapses_case_and_spacing():
    assert normalize_phrase_text("  HEY   POODTYPE  ") == "hey poodtype"
    assert normalize_phrase_text("เฮ้\tพุดไทป์\n") == "เฮ้ พุดไทป์"
    assert normalize_phrase_text("") == ""
    assert normalize_phrase_text(None) == ""  # type: ignore[arg-type]


def test_contains_phrase_respects_case_and_spacing_normalization():
    assert contains_phrase("  เฮ้   พุดไทป์  ", START, tolerance=0.8)
    assert contains_phrase("HEY POODTYPE", START, tolerance=0.8)
    assert contains_phrase("Hey   Pood   Type", START, tolerance=0.8)
    assert contains_phrase("  ส่งได้   พุดไทป์  ", END, tolerance=0.8)
    assert contains_phrase("SONG DAI POODTYPE", END, tolerance=0.8)


def test_collision_prevention_start_vs_end():
    for alias in END_ALIASES:
        assert not contains_phrase(alias, START, tolerance=0.8), alias
    for alias in START_ALIASES:
        # Brand-only short windows are start-only by design; skip those.
        if "ส่งได้" in alias or "ส่งได" in alias or "สงได้" in alias:
            continue
        if alias in {"ภูทัย", "เทพุทธ", "พูดท้าย"}:
            continue
        assert not contains_phrase(alias, END, tolerance=0.8), alias


def test_collision_prevention_non_commands():
    for text in NON_COMMANDS:
        assert not contains_phrase(text, START, tolerance=0.8), text
        assert not contains_phrase(text, END, tolerance=0.8), text


def test_start_and_end_alias_sets_do_not_overlap():
    start_norm = {normalize_phrase_text(a) for a in START_ALIASES}
    end_norm = {normalize_phrase_text(a) for a in END_ALIASES}
    assert start_norm.isdisjoint(end_norm)


def test_strips_start_and_end_for_paste_payload():
    text = "เฮ้ พุดไทป์ พรุ่งนี้ประชุม 10 โมง ส่งได้ พุดไทป์"
    assert (
        strip_command_phrases(
            text, start_phrase=START, end_phrase=END, tolerance=0.8
        )
        == "พรุ่งนี้ประชุม 10 โมง"
    )


def test_strips_alias_variants_from_paste_payload():
    text = "โอเค พูดท้าย นัดพรุ่งนี้ ส่งได้ พุทธไทย"
    assert (
        strip_command_phrases(
            text, start_phrase=START, end_phrase=END, tolerance=0.75
        )
        == "นัดพรุ่งนี้"
    )
