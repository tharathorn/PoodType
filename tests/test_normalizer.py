"""Offline tests for Thai spoken numeral and entity pronunciation normalizer."""

from __future__ import annotations

import pytest

from thai_voice_bridge.normalizer import (
    normalize_spoken_text,
    parse_thai_number,
)


@pytest.mark.parametrize(
    ("spoken", "expected"),
    [
        ("ศูนย์", 0),
        ("หนึ่ง", 1),
        ("สอง", 2),
        ("สาม", 3),
        ("สี่", 4),
        ("ห้า", 5),
        ("หก", 6),
        ("เจ็ด", 7),
        ("แปด", 8),
        ("เก้า", 9),
        ("สิบ", 10),
        ("สิบเอ็ด", 11),
        ("สิบสอง", 12),
        ("ยี่สิบ", 20),
        ("ยี่สิบสาม", 23),
        ("สามสิบ", 30),
        ("เก้าสิบเก้า", 99),
        ("ร้อย", 100),
        ("หนึ่งร้อย", 100),
        ("หนึ่งร้อยยี่สิบห้า", 125),
        ("สองร้อยสิบเอ็ด", 211),
        ("พัน", 1000),
        ("หนึ่งพัน", 1000),
        ("สองพันสามร้อย", 2300),
        ("หมื่น", 10_000),
        ("หนึ่งหมื่น", 10_000),
        ("แสน", 100_000),
        ("หนึ่งแสน", 100_000),
        ("ล้าน", 1_000_000),
        ("หนึ่งล้าน", 1_000_000),
        ("สองล้านสามแสนสี่หมื่นห้าพันหกร้อยเจ็ดสิบแปด", 2_345_678),
    ],
)
def test_parse_thai_number_digits_and_compounds(spoken: str, expected: int):
    assert parse_thai_number(spoken) == expected


def test_parse_thai_number_rejects_non_numeric():
    assert parse_thai_number("") is None
    assert parse_thai_number("พรุ่งนี้") is None
    assert parse_thai_number("บาท") is None


def test_normalize_simple_numerals_in_text():
    assert normalize_spoken_text("มีหนึ่งแอปเปิล") == "มี 1 แอปเปิล"
    assert normalize_spoken_text("ได้สองชิ้น") == "ได้ 2 ชิ้น"
    assert normalize_spoken_text("ยี่สิบคน") == "20 คน"


def test_normalize_compound_numbers():
    assert normalize_spoken_text("หนึ่งร้อยยี่สิบห้าบาท") == "125 บาท"
    assert normalize_spoken_text("สองพันสามร้อยคน") == "2300 คน"
    assert (
        normalize_spoken_text("หนึ่งล้านสองแสนสามหมื่นสี่พัน")
        == "1234000"
    )


def test_normalize_currency_expressions():
    assert normalize_spoken_text("สิบบาท") == "10 บาท"
    assert normalize_spoken_text("ยี่สิบห้าบาท") == "25 บาท"
    assert normalize_spoken_text("หนึ่งร้อยบาทห้าสิบสตางค์") == "100 บาท 50 สตางค์"
    assert normalize_spoken_text("จ่ายสิบบาทค่ะ") == "จ่าย 10 บาท ค่ะ"


def test_normalize_time_expressions():
    assert normalize_spoken_text("สิบโมง") == "10:00 โมง"
    assert normalize_spoken_text("เก้าโมง") == "9:00 โมง"
    assert normalize_spoken_text("นัดสิบโมงเช้า") == "นัด 10:00 โมง เช้า"
    assert normalize_spoken_text("สองทุ่ม") == "20:00 ทุ่ม"
    assert normalize_spoken_text("สามโมงเย็น") == "15:00 โมง เย็น"


def test_normalize_phone_digit_sequences():
    assert (
        normalize_spoken_text("ศูนย์แปดเก้าหนึ่งสองสามสี่ห้าหกเจ็ด")
        == "0891234567"
    )
    assert (
        normalize_spoken_text("เบอร์โทรศูนย์เก้าแปดเจ็ดหกห้าสี่สามสองหนึ่ง")
        == "เบอร์โทร 0987654321"
    )


def test_normalize_preserves_non_numeric_thai():
    assert normalize_spoken_text("พรุ่งนี้ประชุม") == "พรุ่งนี้ประชุม"
    assert normalize_spoken_text("") == ""
    assert normalize_spoken_text("   ") == ""


def test_normalize_mixed_phrase_with_multiple_entities():
    text = "นัดสิบโมง จ่ายยี่สิบห้าบาท โทรศูนย์แปดหนึ่งสองสามสี่ห้าหกเจ็ดแปด"
    assert (
        normalize_spoken_text(text)
        == "นัด 10:00 โมง จ่าย 25 บาท โทร 0812345678"
    )


def test_normalize_spaced_spoken_numbers():
    assert normalize_spoken_text("หนึ่ง ร้อย ยี่ สิบ ห้า") == "125"
    assert normalize_spoken_text("สิบ บาท") == "10 บาท"
    assert normalize_spoken_text("สิบ โมง") == "10:00 โมง"


def test_normalize_edge_cases_edio_and_leading_units():
    assert normalize_spoken_text("สิบเอ็ด") == "11"
    assert normalize_spoken_text("เอ็ด") == "1"
    assert normalize_spoken_text("ร้อยเอ็ด") == "101"
    assert normalize_spoken_text("พันเอ็ด") == "1001"
