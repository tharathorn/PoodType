"""Clipboard paste into the current foreground window with restore."""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Iterator

import keyboard
import pyperclip


class PasteError(RuntimeError):
    """Raised when paste cannot proceed safely."""


@contextmanager
def clipboard_swap(text: str) -> Iterator[str | None]:
    """Temporarily set clipboard to text, then restore previous contents."""
    previous: str | None
    try:
        previous = pyperclip.paste()
    except Exception:
        previous = None
    try:
        pyperclip.copy(text)
        yield previous
    finally:
        try:
            if previous is None:
                pyperclip.copy("")
            else:
                pyperclip.copy(previous)
        except Exception:
            # Best-effort restore; do not raise from finally during success path tests
            pass


def paste_text(
    text: str,
    *,
    auto_send: bool = False,
    settle_seconds: float = 0.05,
) -> None:
    """Paste into whatever window currently has focus. Never focuses a fixed app."""
    cleaned = (text or "").strip()
    if not cleaned:
        raise PasteError("Refusing to paste empty transcript")

    with clipboard_swap(cleaned):
        time.sleep(settle_seconds)
        keyboard.press_and_release("ctrl+v")
        time.sleep(settle_seconds)
        if auto_send:
            time.sleep(settle_seconds)
            keyboard.press_and_release("enter")
