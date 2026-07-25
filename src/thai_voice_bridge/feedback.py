"""Audio feedback (beeps) — Windows winsound with safe no-op fallback."""

from __future__ import annotations

import threading
from thai_voice_bridge.config import FeedbackConfig

try:
    import winsound
except ImportError:  # non-Windows
    winsound = None  # type: ignore[assignment]


def beep(frequency: int, duration_ms: int) -> None:
    if winsound is None:
        return
    threading.Thread(
        target=winsound.Beep,
        args=(int(frequency), int(duration_ms)),
        daemon=True,
    ).start()


class Feedback:
    def __init__(self, config: FeedbackConfig) -> None:
        self.config = config

    def _tone(self, pair: tuple[int, int]) -> None:
        if not self.config.enabled:
            return
        beep(pair[0], pair[1])

    def start(self) -> None:
        self._tone(self.config.start)

    def stop(self) -> None:
        self._tone(self.config.stop)

    def success(self) -> None:
        self._tone(self.config.success)

    def error(self) -> None:
        self._tone(self.config.error)

    def busy(self) -> None:
        self._tone(self.config.busy)
