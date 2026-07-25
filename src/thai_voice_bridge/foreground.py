"""Foreground window targeting — never hard-codes a specific application."""

from __future__ import annotations

import sys
from dataclasses import dataclass

import psutil


@dataclass(frozen=True)
class ForegroundInfo:
    hwnd: int
    process_name: str
    process_id: int
    window_title: str


def _windows_foreground() -> ForegroundInfo | None:
    if sys.platform != "win32":
        return None
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    hwnd = int(user32.GetForegroundWindow())
    if not hwnd:
        return None

    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    process_id = int(pid.value)

    length = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    title = buf.value or ""

    process_name = ""
    try:
        process_name = psutil.Process(process_id).name()
    except (psutil.Error, ValueError):
        process_name = ""

    return ForegroundInfo(
        hwnd=hwnd,
        process_name=process_name,
        process_id=process_id,
        window_title=title,
    )


def get_foreground_info() -> ForegroundInfo | None:
    """Return the currently focused window. Does not steal focus or read app content."""
    return _windows_foreground()


def describe_target(info: ForegroundInfo | None) -> str:
    if info is None:
        return "unknown"
    name = info.process_name or "unknown"
    return f"{name} hwnd={info.hwnd}"
