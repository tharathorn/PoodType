from unittest.mock import MagicMock, patch

from thai_voice_bridge.app import AppState
from thai_voice_bridge.config import config_from_dict
from thai_voice_bridge.tray import ICON_ASSET_PATH, TrayApplication, _make_icon


def test_branded_tray_icon_asset_is_packaged():
    assert ICON_ASSET_PATH.is_file()
    icon = _make_icon((40, 167, 69, 255))
    assert icon.size == (64, 64)
    assert icon.getpixel((32, 32))[:3] != (40, 167, 69)


def test_wake_listen_icon_is_solid_blue():
    tray = TrayApplication(
        MagicMock(),
        config_from_dict({"language": "th", "task": "transcribe", "mode": "wake_word"}),
    )
    tray._state = AppState.IDLE
    icon = tray._icon_image()
    assert icon.getpixel((32, 32))[:3] == (30, 144, 255)


def test_preload_failure_does_not_enable_input():
    app = MagicMock()
    app.preload_model.side_effect = RuntimeError("model unavailable")
    tray = TrayApplication(
        app,
        config_from_dict({"language": "th", "task": "transcribe"}),
    )

    tray._boot()

    app.start_input.assert_not_called()
    app.start_hotkey.assert_not_called()
    app._set_state.assert_called_once_with(AppState.ERROR)


def test_boot_uses_start_input():
    app = MagicMock()
    tray = TrayApplication(
        app,
        config_from_dict({"language": "th", "task": "transcribe", "mode": "hotkey"}),
    )

    tray._boot()

    app.start_input.assert_called_once()
    app.start_hotkey.assert_not_called()


def test_set_mode_wake_word_updates_config_and_calls_app(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "language: th\ntask: transcribe\nmode: hotkey\nhotkey: f8\n",
        encoding="utf-8",
    )
    cfg = config_from_dict(
        {"language": "th", "task": "transcribe", "mode": "hotkey", "hotkey": "f8"},
        source_path=config_path,
    )
    app = MagicMock()
    tray = TrayApplication(app, cfg)

    tray._set_mode_wake_word()

    app.set_mode.assert_called_once_with("wake_word")
    assert cfg.mode == "wake_word"
    assert "mode: wake_word" in config_path.read_text(encoding="utf-8")


def test_title_shows_wake_word_mode():
    tray = TrayApplication(
        MagicMock(),
        config_from_dict({"language": "th", "task": "transcribe", "mode": "wake_word"}),
    )
    tray._state = AppState.IDLE
    assert "wake_word" in tray._title()
