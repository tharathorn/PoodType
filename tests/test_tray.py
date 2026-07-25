from unittest.mock import MagicMock

from thai_voice_bridge.app import AppState
from thai_voice_bridge.config import config_from_dict
from thai_voice_bridge.tray import TrayApplication


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
