"""Foreground targeting — no hard-coded claude.exe focus."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from thai_voice_bridge.foreground import ForegroundInfo, describe_target, get_foreground_info


def test_describe_target():
    info = ForegroundInfo(
        hwnd=42, process_name="Cursor.exe", process_id=99, window_title="x"
    )
    assert "Cursor.exe" in describe_target(info)
    assert describe_target(None) == "unknown"


def test_get_foreground_info_uses_current_window_only():
    fake = ForegroundInfo(
        hwnd=7, process_name="Code.exe", process_id=1, window_title="editor"
    )
    with patch("thai_voice_bridge.foreground._windows_foreground", return_value=fake):
        got = get_foreground_info()
    assert got is not None
    assert got.process_name == "Code.exe"
    assert got.hwnd == 7


def test_no_claude_hardcode_in_source():
    root = Path(__file__).resolve().parents[1] / "src" / "thai_voice_bridge"
    offenders = []
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "claude.exe" in text.lower() or "find_claude" in text.lower():
            offenders.append(path.name)
    assert offenders == []
