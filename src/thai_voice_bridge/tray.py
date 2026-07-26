"""Windows system tray UI (no console flash when launched via pythonw)."""

from __future__ import annotations

import logging
import re
import threading
from pathlib import Path

from PIL import Image, ImageDraw

from thai_voice_bridge.app import AppState, VoiceBridgeApp
from thai_voice_bridge.config import (
    AppConfig,
    default_user_config_path,
    ensure_user_config,
)

logger = logging.getLogger("thai_voice_bridge.tray")
ICON_ASSET_PATH = Path(__file__).resolve().parent / "assets" / "thai_voice_bridge.png"


def _make_icon(
    color: tuple[int, int, int, int],
    *,
    solid: bool = False,
) -> Image.Image:
    size = 64
    if solid:
        # Full-bleed status — tiny corner dots are unreadable in the Windows tray.
        image = Image.new("RGBA", (size, size), color)
        draw = ImageDraw.Draw(image)
        draw.ellipse((8, 8, 56, 56), fill=(255, 255, 255, 255))
        draw.ellipse((14, 14, 50, 50), fill=color)
        return image
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
WAKE_LISTEN_COLOR = (30, 144, 255, 255)  # blue = wake armed / listening


class TrayApplication:
    def __init__(self, app: VoiceBridgeApp, config: AppConfig) -> None:
        self.app = app
        self.config = config
        self._icon = None
        self._state = AppState.IDLE

    def _mode_label(self) -> str:
        if self.config.mode == "wake_word":
            return "wake_word"
        return self.config.hotkey.upper()

    def _icon_color(self) -> tuple[int, int, int, int]:
        if self._state == AppState.IDLE and self.config.mode == "wake_word":
            return WAKE_LISTEN_COLOR
        return STATE_COLORS.get(self._state, STATE_COLORS[AppState.IDLE])

    def _icon_image(self) -> Image.Image:
        color = self._icon_color()
        solid = self.config.mode == "wake_word" or self._state in {
            AppState.RECORDING,
            AppState.BUSY,
        }
        return _make_icon(color, solid=solid)

    def _title(self) -> str:
        return f"PoodType [{self._state.value}] — {self._mode_label()}"

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

    def _persist_mode(self, mode: str) -> None:
        path = self.config.source_path
        if path is None:
            return
        try:
            if path.exists():
                text = path.read_text(encoding="utf-8")
            else:
                text = ""
            if re.search(r"(?m)^mode:\s*.*$", text):
                text = re.sub(r"(?m)^mode:\s*.*$", f"mode: {mode}", text, count=1)
            else:
                text = text.rstrip() + f"\nmode: {mode}\n"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        except OSError as exc:
            logger.error("Cannot persist mode=%s: %s", mode, exc)

    def _apply_mode(self, mode: str) -> None:
        if self.config.mode == mode:
            logger.info("mode_unchanged mode=%s", mode)
            return
        logger.info("mode_switch requested=%s", mode)
        self.app.set_mode(mode)
        self.config.mode = mode
        self._persist_mode(mode)
        if self._icon is not None:
            self._icon.title = self._title()
            self._icon.icon = self._icon_image()
            if mode == "wake_word":
                try:
                    self._icon.notify(
                        "พูด «เฮ้ พุดไทป์» แล้วหยุดเงียบครึ่งวินาที",
                        "PoodType — Wake word",
                    )
                except Exception:  # noqa: BLE001
                    logger.debug("tray notify unavailable", exc_info=True)
                # Audible confirmation that wake mode is armed (F8-like feedback).
                self.app.feedback.success()

    def _set_mode_hotkey(self, _icon=None, _item=None) -> None:  # noqa: ANN001
        self._apply_mode("hotkey")

    def _set_mode_wake_word(self, _icon=None, _item=None) -> None:  # noqa: ANN001
        self._apply_mode("wake_word")

    def _exit(self, icon=None, _item=None) -> None:  # noqa: ANN001
        self.app.stop()
        if icon is not None:
            icon.stop()

    def _on_state(self, state: AppState) -> None:
        self._state = state
        if self._icon is None:
            return
        self._icon.icon = self._icon_image()
        self._icon.title = self._title()

    def _boot(self) -> None:
        try:
            self.app.preload_model()
        except Exception as exc:  # noqa: BLE001
            logger.error("Model preload failed; input remains disabled: %s", exc)
            self.app._set_state(AppState.ERROR)
            return
        self.app.start_input()
        # Refresh tray after input mode starts (wake = solid blue).
        if self._icon is not None:
            self._icon.icon = self._icon_image()
            self._icon.title = self._title()

    def run(self) -> None:
        import pystray

        self.app.on_state_change = self._on_state
        hotkey_label = f"Mode: Hotkey ({self.config.hotkey.upper()})"
        menu = pystray.Menu(
            pystray.MenuItem(
                lambda item: "Resume" if self._state == AppState.STOPPED else "Pause",
                self._toggle,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Mode: Wake word",
                self._set_mode_wake_word,
                checked=lambda item: self.config.mode == "wake_word",
            ),
            pystray.MenuItem(
                hotkey_label,
                self._set_mode_hotkey,
                checked=lambda item: self.config.mode == "hotkey",
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Settings…", self._open_settings),
            pystray.MenuItem("Exit", self._exit),
        )
        self._icon = pystray.Icon(
            "poodtype",
            self._icon_image(),
            self._title(),
            menu,
        )

        threading.Thread(target=self._boot, daemon=True).start()
        self._icon.run()


def run_tray(config: AppConfig) -> int:
    app = VoiceBridgeApp(config)
    TrayApplication(app, config).run()
    return 0
