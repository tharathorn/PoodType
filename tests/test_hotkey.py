from unittest.mock import MagicMock

from thai_voice_bridge.hotkey import HotkeyController


def test_disable_clears_held_key_and_suppresses_stale_release():
    on_press = MagicMock()
    on_release = MagicMock()
    controller = HotkeyController(
        "f8",
        on_press=on_press,
        on_release=on_release,
        debounce_seconds=0,
    )

    controller._handle_press(None)
    controller.disable()
    controller._handle_release(None)

    on_press.assert_called_once()
    on_release.assert_not_called()
