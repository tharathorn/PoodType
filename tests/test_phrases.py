"""Tests for wake/end phrase matching and Thai text normalization."""

from __future__ import annotations

from thai_voice_bridge.phrases import contains_phrase, strip_command_phrases
from thai_voice_bridge.text_normalizer import (
    normalize_currency,
    normalize_spoken_numbers,
    normalize_spoken_punctuation,
    normalize_text,
    remove_stutter_tokens,
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


# --- Offline Thai text / currency normalization ---


def test_remove_stutter_tokens_collapses_consecutive_duplicates():
    assert remove_stutter_tokens("ไป ไป ไป ตลาด") == "ไป ตลาด"
    assert remove_stutter_tokens("ครับ ครับ พรุ่งนี้") == "ครับ พรุ่งนี้"
    assert remove_stutter_tokens("hello hello world") == "hello world"
    assert remove_stutter_tokens("ไม่ซ้ำ") == "ไม่ซ้ำ"
    assert remove_stutter_tokens("") == ""
    assert remove_stutter_tokens("   ") == ""


def test_normalize_spoken_punctuation_tokens():
    assert normalize_spoken_punctuation("จบ จุด") == "จบ."
    assert normalize_spoken_punctuation("รายการ จุลภาค สอง") == "รายการ, สอง"
    assert normalize_spoken_punctuation("โฟลเดอร์ ทับ ไฟล์") == "โฟลเดอร์/ไฟล์"
    assert normalize_spoken_punctuation("รหัส ขีด หนึ่ง") == "รหัส-หนึ่ง"
    assert normalize_spoken_punctuation("เวลา สองจุด สามสิบ") == "เวลา: สามสิบ"
    assert normalize_spoken_punctuation("เปิดวงเล็บ ข้อความ ปิดวงเล็บ") == "(ข้อความ)"
    assert normalize_spoken_punctuation("ใช่ไหม เครื่องหมายคำถาม") == "ใช่ไหม?"
    assert normalize_spoken_punctuation("ว้าว อัศเจรีย์") == "ว้าว!"
    assert normalize_spoken_punctuation("ส่วนแบ่ง เปอร์เซ็นต์") == "ส่วนแบ่ง%"


def test_normalize_spoken_numbers_basic():
    assert normalize_spoken_numbers("ศูนย์") == "0"
    assert normalize_spoken_numbers("หนึ่ง") == "1"
    assert normalize_spoken_numbers("สิบ") == "10"
    assert normalize_spoken_numbers("สิบเอ็ด") == "11"
    assert normalize_spoken_numbers("ยี่สิบสาม") == "23"
    assert normalize_spoken_numbers("หนึ่งร้อยยี่สิบห้า") == "125"
    assert normalize_spoken_numbers("สองพันห้าร้อย") == "2500"
    assert normalize_spoken_numbers("หนึ่งหมื่น") == "10000"


def test_normalize_spoken_numbers_preserves_surrounding_words():
    assert normalize_spoken_numbers("นัด พรุ่งนี้ สิบโมง") == "นัด พรุ่งนี้ 10โมง"
    assert normalize_spoken_numbers("ห้อง สาม") == "ห้อง 3"


def test_normalize_currency_baht_and_satang():
    assert normalize_currency("หนึ่งร้อยบาท") == "100 บาท"
    assert normalize_currency("ห้าสิบบาท") == "50 บาท"
    assert normalize_currency("ห้าสิบบาทห้าสิบสตางค์") == "50.50 บาท"
    assert normalize_currency("หนึ่งบาทยี่สิบห้าสตางค์") == "1.25 บาท"
    assert normalize_currency("เจ็ดสิบห้าสตางค์") == "0.75 บาท"
    assert normalize_currency("ราคา สองร้อยบาท") == "ราคา 200 บาท"


def test_normalize_text_pipeline_offline():
    raw = "ไป ไป ตลาด จุด ราคาสองร้อยบาทห้าสิบสตางค์ ครับ ครับ"
    assert normalize_text(raw) == "ไป ตลาด. ราคา200.50 บาท ครับ"

    spaced = "จ่าย ห้าสิบ บาท ห้าสิบ สตางค์"
    assert normalize_text(spaced) == "จ่าย 50.50 บาท"


def test_normalize_text_handles_empty_and_passthrough():
    assert normalize_text("") == ""
    assert normalize_text("   ") == ""
    assert normalize_text("สวัสดีครับ") == "สวัสดีครับ"
    assert normalize_text("hello 123") == "hello 123"
