"""Single-instance lock for Windows (named mutex) with file-lock fallback."""

from __future__ import annotations

import atexit
import sys
import tempfile
from pathlib import Path

MUTEX_NAME = "Local\\ThaiVoiceBridgeSingleInstance"
LOCK_FILENAME = "thai_voice_bridge.instance.lock"


class SingleInstanceError(RuntimeError):
    pass


class SingleInstanceLock:
    def __init__(self, name: str = MUTEX_NAME) -> None:
        self.name = name
        self._handle = None
        self._lock_path: Path | None = None
        self._fp = None

    def acquire(self) -> None:
        if sys.platform == "win32":
            self._acquire_mutex()
        else:
            self._acquire_file()
        atexit.register(self.release)

    def _acquire_mutex(self) -> None:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.CreateMutexW(None, False, self.name)
        last_error = kernel32.GetLastError()
        ERROR_ALREADY_EXISTS = 183
        if not handle:
            raise SingleInstanceError("Failed to create instance mutex")
        if last_error == ERROR_ALREADY_EXISTS:
            kernel32.CloseHandle(handle)
            raise SingleInstanceError("thai-voice-bridge is already running")
        self._handle = handle

    def _acquire_file(self) -> None:
        path = Path(tempfile.gettempdir()) / LOCK_FILENAME
        fp = path.open("a+", encoding="utf-8")
        try:
            if sys.platform == "win32":
                import msvcrt

                fp.seek(0)
                msvcrt.locking(fp.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            fp.close()
            raise SingleInstanceError("thai-voice-bridge is already running") from exc
        self._fp = fp
        self._lock_path = path

    def release(self) -> None:
        if self._handle is not None and sys.platform == "win32":
            import ctypes

            ctypes.windll.kernel32.CloseHandle(self._handle)
            self._handle = None
        if self._fp is not None:
            try:
                if sys.platform == "win32":
                    import msvcrt

                    self._fp.seek(0)
                    msvcrt.locking(self._fp.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(self._fp.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
            try:
                self._fp.close()
            except OSError:
                pass
            self._fp = None
