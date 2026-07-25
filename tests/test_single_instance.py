"""Single-instance lock behavior."""

from __future__ import annotations

import sys

import pytest

from thai_voice_bridge.single_instance import SingleInstanceError, SingleInstanceLock


@pytest.mark.skipif(sys.platform != "win32", reason="Windows mutex path")
def test_second_mutex_raises():
    name = "Local\\ThaiVoiceBridgeTestMutexUnique"
    first = SingleInstanceLock(name=name)
    first.acquire()
    try:
        second = SingleInstanceLock(name=name)
        with pytest.raises(SingleInstanceError):
            second.acquire()
    finally:
        first.release()


def test_file_lock_second_acquire_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "thai_voice_bridge.single_instance.tempfile.gettempdir",
        lambda: str(tmp_path),
    )
    first = SingleInstanceLock()
    second = SingleInstanceLock()
    first._acquire_file()
    try:
        with pytest.raises(SingleInstanceError):
            second._acquire_file()
    finally:
        first.release()
