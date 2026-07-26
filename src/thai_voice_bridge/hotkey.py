"""Global toggle hotkey binding (press to start, press again to stop)."""

from __future__ import annotations

import threading
import time
from typing import Callable


import keyboard


class HotkeyController:
    def __init__(
        self,
        hotkey: str,
        *,
        on_press: Callable[[], None],
        on_release: Callable[[float], None],
        min_hold_seconds: float = 0.3,
        debounce_seconds: float = 0.5,
    ) -> None:
        self.hotkey = hotkey.lower()
        self.on_press = on_press
        self.on_release = on_release
        self.min_hold_seconds = min_hold_seconds
        self.debounce_seconds = debounce_seconds
        self._key_down = False
        self._recording = False
        self._press_mono = 0.0
        self._last_edge_mono = 0.0
        self._enabled = True
        self._lock = threading.Lock()

    def enable(self) -> None:
        with self._lock:
            self._enabled = True

    def disable(self) -> None:
        with self._lock:
            self._enabled = False
            self._key_down = False
            self._recording = False
            self._press_mono = 0.0

    @property
    def enabled(self) -> bool:
        with self._lock:
            return self._enabled

    def _handle_press(self, _event) -> None:  # noqa: ANN001
        now = time.monotonic()
        start = False
        stop_held = 0.0
        with self._lock:
            if not self._enabled:
                return
            # Ignore OS key-repeat while the physical key is held.
            if self._key_down:
                return
            if (now - self._last_edge_mono) < self.debounce_seconds:
                return
            self._key_down = True
            self._last_edge_mono = now
            if self._recording:
                self._recording = False
                stop_held = now - self._press_mono
            else:
                self._recording = True
                self._press_mono = now
                start = True
        if start:
            self.on_press()
        else:
            self.on_release(stop_held)

    def _handle_release(self, _event) -> None:  # noqa: ANN001
        # Toggle mode: release only clears key-down so the next press can fire.
        with self._lock:
            self._key_down = False

    def start(self) -> None:
        keyboard.on_press_key(self.hotkey, self._handle_press, suppress=True)
        keyboard.on_release_key(self.hotkey, self._handle_release, suppress=True)

    def wait(self) -> None:
        keyboard.wait()
