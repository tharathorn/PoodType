from unittest.mock import MagicMock

from thai_voice_bridge.hotkey import HotkeyController


def test_disable_clears_recording_and_suppresses_stale_stop():
    on_press = MagicMock()
    on_release = MagicMock()
    controller = HotkeyController(
        "f8",
        on_press=on_press,
        on_release=on_release,
        debounce_seconds=0,
    )

    controller._handle_press(None)  # start
    controller._handle_release(None)
    controller.disable()
    controller._handle_press(None)  # would have been stop

    on_press.assert_called_once()
    on_release.assert_not_called()


def test_toggle_press_starts_second_press_stops():
    on_press = MagicMock()
    on_release = MagicMock()
    controller = HotkeyController(
        "f8",
        on_press=on_press,
        on_release=on_release,
        debounce_seconds=0,
    )

    controller._handle_press(None)
    controller._handle_release(None)
    on_press.assert_called_once()
    on_release.assert_not_called()

    controller._handle_press(None)
    controller._handle_release(None)
    on_release.assert_called_once()
    held = on_release.call_args.args[0]
    assert held >= 0.0


def test_key_repeat_while_held_does_not_double_toggle():
    on_press = MagicMock()
    on_release = MagicMock()
    controller = HotkeyController(
        "f8",
        on_press=on_press,
        on_release=on_release,
        debounce_seconds=0,
    )

    controller._handle_press(None)
    controller._handle_press(None)  # repeat before release
    controller._handle_press(None)
    on_press.assert_called_once()
    on_release.assert_not_called()
