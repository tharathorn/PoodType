"""Windows system tray UI (no console flash when launched via pythonw)."""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from PIL import Image, ImageDraw

from thai_voice_bridge.app import AppState, VoiceBridgeApp
from thai_voice_bridge.config import AppConfig, default_user_config_path, ensure_user_config

logger = logging.getLogger("thai_voice_bridge.tray")
ICON_ASSET_PATH = Path(__file__).resolve().parent / "assets" / "thai_voice_bridge.png"


def _make_icon(color: tuple[int, int, int, int]) -> Image.Image:
    size = 64
    try:
        image = Image.open(ICON_ASSET_PATH).convert("RGBA")
        image = image.resize((size, size), Image.Resampling.LANCZOS)
    except OSError:
        image = Image.new("RGBA", (size, size), (15, 48, 120, 255))
    draw = ImageDraw.Draw(image)
    # Small high-contrast status indicator: green idle, red recording,
    # amber busy, gray stopped/error.
    draw.ellipse((45, 45, 62, 62), fill=(255, 255, 255, 255))
    draw.ellipse((48, 48, 59, 59), fill=color)
    return image


STATE_COLORS = {
    AppState.IDLE: (40, 167, 69, 255),
    AppState.RECORDING: (220, 53, 69, 255),
    AppState.BUSY: (255, 193, 7, 255),
    AppState.ERROR: (108, 117, 125, 255),
    AppState.STOPPED: (108, 117, 125, 255),
}


class TrayApplication:
    def __init__(self, app: VoiceBridgeApp, config: AppConfig) -> None:
        self.app = app
        self.config = config
        self._icon = None
        self._state = AppState.IDLE

    def _title(self) -> str:
        return f"PoodType [{self._state.value}] — {self.config.hotkey.upper()}"

    def _open_settings(self, _icon=None, _item=None) -> None:  # noqa: ANN001
        path = ensure_user_config(default_user_config_path())
        try:
            import os

            os.startfile(str(path))  # noqa: S606 — intentional Windows open
        except OSError as exc:
            logger.error("Cannot open settings: %s", exc)

    def _toggle(self, _icon=None, _item=None) -> None:  # noqa: ANN001
        if self._state == AppState.STOPPED:
            self.app.resume_listening()
        else:
            self.app.pause_listening()

    def _exit(self, icon=None, _item=None) -> None:  # noqa: ANN001
        self.app.stop()
        if icon is not None:
            icon.stop()

    def _on_state(self, state: AppState) -> None:
        self._state = state
        if self._icon is None:
            return
        self._icon.icon = _make_icon(STATE_COLORS.get(state, STATE_COLORS[AppState.IDLE]))
        self._icon.title = self._title()

    def _boot(self) -> None:
        try:
            self.app.preload_model()
        except Exception as exc:  # noqa: BLE001
            logger.error("Model preload failed; hotkey remains disabled: %s", exc)
            self.app._set_state(AppState.ERROR)
            return
        self.app.start_hotkey()

    def run(self) -> None:
        import pystray

        self.app.on_state_change = self._on_state
        menu = pystray.Menu(
            pystray.MenuItem(
                lambda item: "Resume" if self._state == AppState.STOPPED else "Pause",
                self._toggle,
            ),
            pystray.MenuItem("Settings…", self._open_settings),
            pystray.MenuItem("Exit", self._exit),
        )
        self._icon = pystray.Icon(
            "poodtype",
            _make_icon(STATE_COLORS[AppState.IDLE]),
            self._title(),
            menu,
        )

        threading.Thread(target=self._boot, daemon=True).start()
        self._icon.run()


def run_tray(config: AppConfig) -> int:
    app = VoiceBridgeApp(config)
    TrayApplication(app, config).run()
    return 0
