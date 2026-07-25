"""Clipboard save/restore around paste."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from thai_voice_bridge.paste import PasteError, clipboard_swap, paste_text


def test_clipboard_swap_restores_previous():
    store = {"value": "ORIGINAL"}

    def fake_paste():
        return store["value"]

    def fake_copy(text):
        store["value"] = text

    with patch("thai_voice_bridge.paste.pyperclip.paste", side_effect=fake_paste), patch(
        "thai_voice_bridge.paste.pyperclip.copy", side_effect=fake_copy
    ):
        with clipboard_swap("NEW"):
            assert store["value"] == "NEW"
        assert store["value"] == "ORIGINAL"


def test_paste_text_refuses_empty():
    with pytest.raises(PasteError):
        paste_text("   ")


def test_paste_text_restores_and_optional_send():
    store = {"value": "KEEP"}
    presses: list[str] = []

    def fake_paste():
        return store["value"]

    def fake_copy(text):
        store["value"] = text

    def fake_press(combo):
        presses.append(combo)

    with patch("thai_voice_bridge.paste.pyperclip.paste", side_effect=fake_paste), patch(
        "thai_voice_bridge.paste.pyperclip.copy", side_effect=fake_copy
    ), patch("thai_voice_bridge.paste.keyboard.press_and_release", side_effect=fake_press), patch(
        "thai_voice_bridge.paste.time.sleep", return_value=None
    ):
        paste_text("สวัสดี", auto_send=False)
        assert store["value"] == "KEEP"
        assert presses == ["ctrl+v"]

        paste_text("ส่งเลย", auto_send=True)
        assert presses == ["ctrl+v", "ctrl+v", "enter"]
        assert store["value"] == "KEEP"


def test_clipboard_read_failure_refuses_to_overwrite():
    with patch(
        "thai_voice_bridge.paste.pyperclip.paste", side_effect=RuntimeError("locked")
    ), patch("thai_voice_bridge.paste.pyperclip.copy") as copy:
        with pytest.raises(PasteError, match="read clipboard"):
            paste_text("ห้ามเขียนทับ")
    copy.assert_not_called()


def test_clipboard_restore_failure_is_reported():
    copies = iter([None, RuntimeError("restore failed")])

    def fake_copy(_text):
        result = next(copies)
        if isinstance(result, Exception):
            raise result

    with patch("thai_voice_bridge.paste.pyperclip.paste", return_value="ORIGINAL"), patch(
        "thai_voice_bridge.paste.pyperclip.copy", side_effect=fake_copy
    ), patch("thai_voice_bridge.paste.keyboard.press_and_release"), patch(
        "thai_voice_bridge.paste.time.sleep", return_value=None
    ):
        with pytest.raises(PasteError, match="restore clipboard"):
            paste_text("ข้อความ")
