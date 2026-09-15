"""Clipboard save/restore around paste."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from thai_voice_bridge.foreground import ForegroundInfo
from thai_voice_bridge.paste import (
    ELECTRON_HOLD_SECONDS,
    PasteError,
    VK_CONTROL,
    VK_RETURN,
    VK_V,
    _hold_seconds_for_process,
    _press_enter,
    _press_paste,
    clipboard_swap,
    paste_text,
)


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


def test_autosend_requires_expected_hwnd():
    """auto_send must never paste/Enter without a focus guard HWND."""
    presses: list[str] = []

    with patch("thai_voice_bridge.paste.pyperclip.paste", return_value="KEEP"), patch(
        "thai_voice_bridge.paste.pyperclip.copy"
    ), patch(
        "thai_voice_bridge.paste._press_paste", side_effect=lambda: presses.append("ctrl+v")
    ), patch(
        "thai_voice_bridge.paste._press_enter", side_effect=lambda: presses.append("enter")
    ), patch("thai_voice_bridge.paste.time.sleep", return_value=None):
        with pytest.raises(PasteError, match="expected_hwnd"):
            paste_text("ข้อความ", auto_send=True, hold_seconds=0.0)

    assert presses == []


def test_paste_text_restores_and_optional_send():
    store = {"value": "KEEP"}
    presses: list[str] = []
    sleeps: list[float] = []

    def fake_paste():
        return store["value"]

    def fake_copy(text):
        store["value"] = text

    with patch("thai_voice_bridge.paste.pyperclip.paste", side_effect=fake_paste), patch(
        "thai_voice_bridge.paste.pyperclip.copy", side_effect=fake_copy
    ), patch(
        "thai_voice_bridge.paste._press_paste", side_effect=lambda: presses.append("ctrl+v")
    ), patch(
        "thai_voice_bridge.paste._press_enter", side_effect=lambda: presses.append("enter")
    ), patch(
        "thai_voice_bridge.paste.time.sleep", side_effect=lambda s: sleeps.append(s)
    ):
        paste_text("สวัสดี", auto_send=False, hold_seconds=0.2)
        assert store["value"] == "KEEP"
        assert presses == ["ctrl+v"]
        assert 0.2 in sleeps

        paste_text(
            "ส่งเลย",
            auto_send=True,
            hold_seconds=0.1,
            expected_hwnd=1,
            foreground_probe=lambda: ForegroundInfo(1, "x.exe", 1, "x"),
        )
        assert presses == ["ctrl+v", "ctrl+v", "enter"]
        assert store["value"] == "KEEP"

def test_focus_change_before_paste_suppresses_paste_and_enter():
    """HWND must be re-read immediately before Ctrl+V; neither action if changed."""
    presses: list[str] = []
    other = ForegroundInfo(2, "Codex.exe", 2, "Codex")

    with patch("thai_voice_bridge.paste.pyperclip.paste", return_value="KEEP"), patch(
        "thai_voice_bridge.paste.pyperclip.copy"
    ), patch(
        "thai_voice_bridge.paste._press_paste", side_effect=lambda: presses.append("ctrl+v")
    ), patch(
        "thai_voice_bridge.paste._press_enter", side_effect=lambda: presses.append("enter")
    ), patch("thai_voice_bridge.paste.time.sleep", return_value=None):
        with pytest.raises(PasteError, match="before paste"):
            paste_text(
                "ข้อความ",
                auto_send=True,
                hold_seconds=0.0,
                expected_hwnd=1,
                foreground_probe=lambda: other,
            )

    assert presses == []


def test_autosend_rechecks_hwnd_immediately_before_enter():
    """Focus may change during hold delay — paste ok, Enter suppressed."""
    presses: list[str] = []
    stable = ForegroundInfo(1, "Cursor.exe", 1, "Cursor")
    changed = ForegroundInfo(2, "Codex.exe", 2, "Codex")
    probes = iter([stable, changed])

    with patch("thai_voice_bridge.paste.pyperclip.paste", return_value="KEEP"), patch(
        "thai_voice_bridge.paste.pyperclip.copy"
    ), patch(
        "thai_voice_bridge.paste._press_paste", side_effect=lambda: presses.append("ctrl+v")
    ), patch(
        "thai_voice_bridge.paste._press_enter", side_effect=lambda: presses.append("enter")
    ), patch("thai_voice_bridge.paste.time.sleep", return_value=None):
        with pytest.raises(PasteError, match="before auto-send"):
            paste_text(
                "ข้อความ",
                auto_send=True,
                hold_seconds=0.0,
                expected_hwnd=1,
                foreground_probe=lambda: next(probes),
            )

    assert presses == ["ctrl+v"]


def test_autosend_enters_when_hwnd_stable():
    target = ForegroundInfo(7, "Cursor.exe", 1, "Cursor")
    presses: list[str] = []
    # Probe runs before Ctrl+V and again before Enter.
    probes = iter([target, target])

    with patch("thai_voice_bridge.paste.pyperclip.paste", return_value="KEEP"), patch(
        "thai_voice_bridge.paste.pyperclip.copy"
    ), patch(
        "thai_voice_bridge.paste._press_paste", side_effect=lambda: presses.append("ctrl+v")
    ), patch(
        "thai_voice_bridge.paste._press_enter", side_effect=lambda: presses.append("enter")
    ), patch("thai_voice_bridge.paste.time.sleep", return_value=None):
        paste_text(
            "ข้อความ",
            auto_send=True,
            hold_seconds=0.0,
            expected_hwnd=7,
            foreground_probe=lambda: next(probes),
        )

    assert presses == ["ctrl+v", "enter"]


def test_sendinput_partial_ctrl_v_fails_closed_without_keyboard_fallback():
    keyups: list[int] = []

    def fake_send_input(events):  # noqa: ANN001
        # Cleanup path injects single KEYUP events via the real helper.
        assert len(events) == 1
        keyups.append(int(events[0].ki.wVk))
        return 1

    with patch("thai_voice_bridge.paste.sys.platform", "win32"), patch(
        "thai_voice_bridge.paste._send_ctrl_key", return_value=2
    ), patch(
        "thai_voice_bridge.paste._send_input", side_effect=fake_send_input
    ), patch("thai_voice_bridge.paste.keyboard.press_and_release") as kb:
        with pytest.raises(PasteError, match=r"partial injection \(2/4"):
            _press_paste()

    kb.assert_not_called()
    assert keyups == [VK_V, VK_CONTROL]


def test_sendinput_partial_cleanup_reports_failed_keyup_counts():
    """Cleanup must check key-up injection results, not swallow failures."""
    calls = {"n": 0}

    def fake_send_input(events):  # noqa: ANN001
        del events
        calls["n"] += 1
        # First key-up succeeds; second reports zero injected events.
        return 1 if calls["n"] == 1 else 0

    with patch("thai_voice_bridge.paste.sys.platform", "win32"), patch(
        "thai_voice_bridge.paste._send_ctrl_key", return_value=2
    ), patch(
        "thai_voice_bridge.paste._send_input", side_effect=fake_send_input
    ), patch("thai_voice_bridge.paste.keyboard.press_and_release") as kb:
        with pytest.raises(PasteError, match=r"cleanup failed:.*0/1"):
            _press_paste()

    kb.assert_not_called()
    assert calls["n"] == 2


def test_sendinput_zero_ctrl_v_falls_back_to_keyboard():
    with patch("thai_voice_bridge.paste.sys.platform", "win32"), patch(
        "thai_voice_bridge.paste._send_ctrl_key", return_value=0
    ), patch("thai_voice_bridge.paste.keyboard.press_and_release") as kb:
        _press_paste()
    kb.assert_called_once_with("ctrl+v")


def test_sendinput_partial_enter_fails_closed_without_keyboard_fallback():
    keyups: list[int] = []

    def fake_send_input(events):  # noqa: ANN001
        assert len(events) == 1
        keyups.append(int(events[0].ki.wVk))
        return 1

    with patch("thai_voice_bridge.paste.sys.platform", "win32"), patch(
        "thai_voice_bridge.paste._send_enter_events", return_value=1
    ), patch(
        "thai_voice_bridge.paste._send_input", side_effect=fake_send_input
    ), patch("thai_voice_bridge.paste.keyboard.press_and_release") as kb:
        with pytest.raises(PasteError, match=r"partial injection \(1/2"):
            _press_enter()

    kb.assert_not_called()
    assert keyups == [VK_RETURN]

def test_electron_process_gets_longer_default_hold():
    assert _hold_seconds_for_process("Cursor.exe", hold_seconds=None) == ELECTRON_HOLD_SECONDS
    assert _hold_seconds_for_process("codex.exe", hold_seconds=None) == ELECTRON_HOLD_SECONDS
    assert _hold_seconds_for_process("notepad.exe", hold_seconds=None) == ELECTRON_HOLD_SECONDS
    assert _hold_seconds_for_process("SomethingElse.exe", hold_seconds=None) == 0.25
    assert _hold_seconds_for_process("Cursor.exe", hold_seconds=0.5) == 0.5


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
    ), patch("thai_voice_bridge.paste._press_paste"), patch(
        "thai_voice_bridge.paste.time.sleep", return_value=None
    ):
        with pytest.raises(PasteError, match="restore clipboard"):
            paste_text("ข้อความ", hold_seconds=0.0)
