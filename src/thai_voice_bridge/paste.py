"""Clipboard paste into the current foreground window with restore."""

from __future__ import annotations

import sys
import time
from collections.abc import Callable
from contextlib import contextmanager
from typing import Iterator

import keyboard
import pyperclip

from thai_voice_bridge.foreground import ForegroundInfo, get_foreground_info

# Electron / Chromium editors often consume Ctrl+V asynchronously.
# Restoring the clipboard too early drops the paste (Cursor, Codex UI, Edge).
_ELECTRON_PROCESS_MARKERS = (
    "cursor",
    "codex",
    "code",
    "chrome",
    "msedge",
    "brave",
    "firefox",
    "electron",
    "slack",
    "discord",
    "notepad",
)

DEFAULT_SETTLE_SECONDS = 0.05
DEFAULT_HOLD_SECONDS = 0.25
ELECTRON_HOLD_SECONDS = 0.35

VK_CONTROL = 0x11
VK_V = 0x56
VK_RETURN = 0x0D
KEYEVENTF_KEYUP = 0x0002
INPUT_KEYBOARD = 1


class PasteError(RuntimeError):
    """Raised when paste cannot proceed safely."""


@contextmanager
def clipboard_swap(text: str) -> Iterator[str | None]:
    """Temporarily set clipboard to text, then restore previous contents."""
    try:
        previous = pyperclip.paste()
    except Exception as exc:
        raise PasteError("Cannot read clipboard safely; paste aborted") from exc
    try:
        try:
            pyperclip.copy(text)
        except Exception as exc:
            raise PasteError("Cannot write transcript to clipboard") from exc
        yield previous
    finally:
        try:
            pyperclip.copy(previous)
        except Exception as exc:
            raise PasteError("Cannot restore clipboard after paste") from exc


def _hold_seconds_for_process(
    process_name: str | None,
    *,
    hold_seconds: float | None,
) -> float:
    if hold_seconds is not None:
        return max(0.0, float(hold_seconds))
    proc = (process_name or "").lower()
    if any(marker in proc for marker in _ELECTRON_PROCESS_MARKERS):
        return ELECTRON_HOLD_SECONDS
    return DEFAULT_HOLD_SECONDS


def _win_input_types():  # noqa: ANN201
    import ctypes
    from ctypes import wintypes

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = (
            ("wVk", wintypes.WORD),
            ("wScan", wintypes.WORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
        )

    class INPUT(ctypes.Structure):
        class _INPUT(ctypes.Union):
            _fields_ = (("ki", KEYBDINPUT),)

        _anonymous_ = ("_input",)
        _fields_ = (
            ("type", wintypes.DWORD),
            ("_input", _INPUT),
        )

    return ctypes, KEYBDINPUT, INPUT


def _send_input(events) -> int:  # noqa: ANN001
    """Inject keyboard INPUT events. Returns the count actually injected."""
    if sys.platform != "win32":
        return 0
    ctypes, _KEYBDINPUT, INPUT = _win_input_types()
    n = len(events)
    array = (INPUT * n)(*events)
    return int(ctypes.windll.user32.SendInput(n, array, ctypes.sizeof(INPUT)))


def _key_event(vk: int, flags: int = 0):  # noqa: ANN201
    _ctypes, KEYBDINPUT, INPUT = _win_input_types()
    event = INPUT()
    event.type = INPUT_KEYBOARD
    event.ki = KEYBDINPUT(vk, 0, flags, 0, None)
    return event


def _send_keyup(vk: int) -> int:
    """Inject a single key-up. Returns events injected (0 or 1)."""
    if sys.platform != "win32":
        return 0
    return _send_input([_key_event(vk, KEYEVENTF_KEYUP)])


def _abort_partial_chord(*vks: int) -> None:
    """Release stuck keys after partial injection; fail closed if cleanup is incomplete."""
    failures: list[str] = []
    for vk in vks:
        try:
            sent = _send_keyup(vk)
        except Exception as exc:  # noqa: BLE001 — surface cleanup evidence
            failures.append(f"0x{vk:02X} key-up raised: {exc}")
            continue
        if sent != 1:
            failures.append(f"0x{vk:02X} key-up injected {sent}/1")
    if failures:
        raise PasteError(
            "SendInput partial injection cleanup failed: " + "; ".join(failures)
        )


def _send_ctrl_key(vk_key: int) -> int:
    """Inject Ctrl+key via SendInput. Returns events injected (0..4)."""
    if sys.platform != "win32":
        return 0
    events = [
        _key_event(VK_CONTROL),
        _key_event(vk_key),
        _key_event(vk_key, KEYEVENTF_KEYUP),
        _key_event(VK_CONTROL, KEYEVENTF_KEYUP),
    ]
    return _send_input(events)


def _send_enter_events() -> int:
    """Inject Enter down+up via SendInput. Returns events injected (0..2)."""
    if sys.platform != "win32":
        return 0
    events = [
        _key_event(VK_RETURN),
        _key_event(VK_RETURN, KEYEVENTF_KEYUP),
    ]
    return _send_input(events)


def _fail_partial_injection(sent: int, expected: int, *cleanup_vks: int) -> None:
    """Abort stuck keys, then raise. Prefer cleanup evidence when key-up fails."""
    try:
        _abort_partial_chord(*cleanup_vks)
    except PasteError as cleanup_exc:
        raise PasteError(
            f"SendInput partial injection ({sent}/{expected} events); "
            f"cleanup failed: {cleanup_exc}"
        ) from cleanup_exc
    raise PasteError(
        f"SendInput partial injection ({sent}/{expected} events); paste aborted"
        if expected == 4
        else f"SendInput partial injection ({sent}/{expected} events); Enter aborted"
    )


def _press_paste() -> None:
    """Prefer SendInput Ctrl+V; fall back only when zero events were injected."""
    if sys.platform == "win32":
        sent = _send_ctrl_key(VK_V)
        if sent == 4:
            return
        if sent > 0:
            # Partial chord may leave Ctrl/V down — never fall back to another paste.
            _fail_partial_injection(sent, 4, VK_V, VK_CONTROL)
    keyboard.press_and_release("ctrl+v")


def _press_enter() -> None:
    if sys.platform == "win32":
        sent = _send_enter_events()
        if sent == 2:
            return
        if sent > 0:
            _fail_partial_injection(sent, 2, VK_RETURN)
    keyboard.press_and_release("enter")


def _assert_foreground_hwnd(
    expected_hwnd: int,
    *,
    foreground_probe: Callable[[], ForegroundInfo | None],
    stage: str,
) -> None:
    current = foreground_probe()
    if current is None or int(current.hwnd) != int(expected_hwnd):
        raise PasteError(
            f"Foreground window changed before {stage}; action aborted"
        )


def paste_text(
    text: str,
    *,
    auto_send: bool = False,
    settle_seconds: float = DEFAULT_SETTLE_SECONDS,
    hold_seconds: float | None = None,
    process_name: str | None = None,
    expected_hwnd: int | None = None,
    foreground_probe: Callable[[], ForegroundInfo | None] | None = None,
) -> None:
    """Paste into whatever window currently has focus. Never focuses a fixed app.

    Holds the transcript on the clipboard long enough for Electron-based editors
    (Cursor, Codex, browsers) to consume Ctrl+V before restoring the previous
    clipboard contents.

    When ``expected_hwnd`` is set, the foreground HWND is re-read immediately
    before Ctrl+V. When ``auto_send`` is true, ``expected_hwnd`` is required and
    HWND is re-checked again immediately before Enter. Missing HWND or focus
    change fails closed (no paste and/or no Enter as appropriate).
    """
    cleaned = (text or "").strip()
    if not cleaned:
        raise PasteError("Refusing to paste empty transcript")

    if auto_send and expected_hwnd is None:
        raise PasteError(
            "auto_send requires expected_hwnd; Enter aborted unguarded"
        )

    hold = _hold_seconds_for_process(process_name, hold_seconds=hold_seconds)
    probe = foreground_probe or get_foreground_info
    with clipboard_swap(cleaned):
        time.sleep(settle_seconds)
        if expected_hwnd is not None:
            _assert_foreground_hwnd(
                expected_hwnd, foreground_probe=probe, stage="paste"
            )
        _press_paste()
        time.sleep(max(settle_seconds, hold))
        if auto_send:
            time.sleep(settle_seconds)
            _assert_foreground_hwnd(
                int(expected_hwnd), foreground_probe=probe, stage="auto-send"
            )
            _press_enter()
            time.sleep(settle_seconds)
