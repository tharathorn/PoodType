"""Offline unit tests for TTS text normalization and punctuation sanitization."""

from __future__ import annotations

import pytest

from thai_voice_bridge.tts_preprocess import (
    arabic_to_thai_spoken,
    expand_digits_for_speech,
    normalize_for_tts,
    normalize_whitespace,
    preprocess_for_synthesis,
    sanitize_punctuation,
    strip_controls,
)


# --- Whitespace / controls ----------------------------------------------------


def test_normalize_whitespace_collapses_and_strips():
    assert normalize_whitespace("  สวัสดี   ครับ\t\n") == "สวัสดี ครับ"
    assert normalize_whitespace("") == ""
    assert normalize_whitespace(None) == ""


def test_strip_controls_removes_zwsp_and_bom():
    raw = "สวัสดี\u200bครับ\ufeff"
    assert "\u200b" not in strip_controls(raw)
    assert "\ufeff" not in strip_controls(raw)
    assert strip_controls(raw) == "สวัสดีครับ"


# --- Punctuation sanitizer ----------------------------------------------------


def test_sanitize_punctuation_smart_quotes_and_dashes():
    quoted = sanitize_punctuation("“ทดสอบ”")
    assert '"' not in quoted
    assert "ทดสอบ" in quoted

    out = sanitize_punctuation("ตอนนี้—ดีมาก…จริงๆ!!!")
    assert "—" not in out
    assert "…" not in out
    assert "!!!" not in out
    assert out.count("!") <= 1


def test_sanitize_punctuation_thai_sentence():
    out = sanitize_punctuation("สวัสดี  “โลก”  !!!")
    assert '"' not in out
    assert out.endswith("!")
    assert "  " not in out


def test_sanitize_punctuation_expands_symbols():
    assert "เปอร์เซ็นต์" in sanitize_punctuation("ลด 50%")
    assert "และ" in sanitize_punctuation("แมว & หมา")
    assert "บวก" in sanitize_punctuation("1+2")


def test_sanitize_punctuation_strips_markdown_and_html():
    assert sanitize_punctuation("**สำคัญ** และ <b>ด่วน</b>") == "สำคัญ และ ด่วน"


def test_sanitize_punctuation_empty_and_none():
    assert sanitize_punctuation("") == ""
    assert sanitize_punctuation(None) == ""


# --- Arabic → Thai spoken numerals --------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, "ศูนย์"),
        (1, "หนึ่ง"),
        (10, "สิบ"),
        (11, "สิบเอ็ด"),
        (20, "ยี่สิบ"),
        (21, "ยี่สิบเอ็ด"),
        (100, "หนึ่งร้อย"),
        (101, "หนึ่งร้อยเอ็ด"),
        (111, "หนึ่งร้อยสิบเอ็ด"),
        (200, "สองร้อย"),
        (1000, "หนึ่งพัน"),
        (10000, "หนึ่งหมื่น"),
        (100000, "หนึ่งแสน"),
        (1000000, "หนึ่งล้าน"),
        (1234, "หนึ่งพันสองร้อยสามสิบสี่"),
        (25000000, "ยี่สิบห้าล้าน"),
        (-7, "ลบเจ็ด"),
    ],
)
def test_arabic_to_thai_spoken(value: int, expected: str):
    assert arabic_to_thai_spoken(value) == expected


def test_expand_digits_in_thai_prose():
    assert expand_digits_for_speech("มี 12 คน") == "มี สิบสอง คน"
    assert expand_digits_for_speech("ราคา 99.5 บาท") == "ราคา เก้าสิบเก้าจุดห้า บาท"


def test_expand_digits_phone_digit_by_digit():
    out = expand_digits_for_speech("โทร 0812345678")
    assert "ศูนย์" in out
    assert "8" not in out
    # Digit-by-digit uses spaces between digit words.
    assert " " in out


def test_expand_digits_negative_and_empty():
    assert expand_digits_for_speech("อุณหภูมิ -3 องศา") == "อุณหภูมิ ลบสาม องศา"
    assert expand_digits_for_speech("") == ""
    assert expand_digits_for_speech(None) == ""


# --- Full synthesis pipeline --------------------------------------------------


def test_preprocess_for_synthesis_basic_thai():
    out = preprocess_for_synthesis("สวัสดี!!! มี 3 ข้อความ…")
    assert "สาม" in out
    assert "!!!" not in out
    assert "…" not in out
    assert "สวัสดี" in out
    assert "ข้อความ" in out


def test_preprocess_expands_email_via_speak_paths():
    out = preprocess_for_synthesis("ติดต่อ admin@example.com เดี๋ยวนี้")
    assert "แอท" in out
    assert "ดอทคอม" in out
    assert "@" not in out


def test_preprocess_can_skip_digit_and_path_expansion():
    raw = "ดู https://a.com มี 5 หน้า"
    no_digits = preprocess_for_synthesis(raw, expand_digits=False)
    assert "5" in no_digits
    assert "ห้า" not in no_digits

    no_paths = preprocess_for_synthesis(raw, expand_paths=False)
    assert "https" in no_paths or "://" in no_paths or "https" in no_paths.replace(" ", "")


def test_preprocess_none_and_blank():
    assert preprocess_for_synthesis(None) == ""
    assert preprocess_for_synthesis("   ") == ""


def test_normalize_for_tts_alias():
    assert normalize_for_tts("ทดสอบ 1") == preprocess_for_synthesis("ทดสอบ 1")


def test_preprocess_preserves_thai_prose_without_numbers():
    text = "วันนี้อากาศดีมากครับ"
    assert preprocess_for_synthesis(text) == text
