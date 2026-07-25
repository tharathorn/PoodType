from unittest.mock import MagicMock

from thai_voice_bridge.app import AppState
from thai_voice_bridge.config import config_from_dict
from thai_voice_bridge.tray import ICON_ASSET_PATH, TrayApplication, _make_icon


def test_branded_tray_icon_asset_is_packaged():
    assert ICON_ASSET_PATH.is_file()
    icon = _make_icon((40, 167, 69, 255))
    assert icon.size == (64, 64)
    assert icon.getpixel((32, 32))[:3] != (40, 167, 69)


def test_preload_failure_does_not_enable_hotkey():
    app = MagicMock()
    app.preload_model.side_effect = RuntimeError("model unavailable")
    tray = TrayApplication(
        app,
        config_from_dict({"language": "th", "task": "transcribe"}),
    )

    tray._boot()

    app.start_hotkey.assert_not_called()
    app._set_state.assert_called_once_with(AppState.ERROR)
