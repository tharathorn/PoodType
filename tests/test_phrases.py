"""Tests for wake/end phrase matching and stripping."""

from __future__ import annotations

from thai_voice_bridge.phrases import contains_phrase, strip_command_phrases

START = "เฮ้ พุดไทป์"
END = "ส่งได้ พุดไทป์"


def test_detects_start_and_end_phrases():
    assert contains_phrase("เฮ้ พุดไทป์", START, tolerance=0.8)
    assert contains_phrase("ครับ ส่งได้ พุดไทป์", END, tolerance=0.8)
    assert not contains_phrase("พรุ่งนี้ประชุม", END, tolerance=0.8)
    assert not contains_phrase("ส่งได้ พุดไทป์", START, tolerance=0.8)


def test_strips_start_and_end_for_paste_payload():
    text = "เฮ้ พุดไทป์ พรุ่งนี้ประชุม 10 โมง ส่งได้ พุดไทป์"
    assert (
        strip_command_phrases(
            text, start_phrase=START, end_phrase=END, tolerance=0.8
        )
        == "พรุ่งนี้ประชุม 10 โมง"
    )
