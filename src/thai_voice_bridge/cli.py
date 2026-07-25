"""CLI entrypoints for PoodType."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from thai_voice_bridge import __version__
from thai_voice_bridge.audio import list_input_devices
from thai_voice_bridge.config import (
    ensure_user_config,
    load_config,
    default_user_config_path,
)
from thai_voice_bridge.single_instance import SingleInstanceError, SingleInstanceLock
from thai_voice_bridge.whisper_engine import apply_hf_cache_env, discover_cached_model


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="poodtype",
        description="PoodType — speak Thai, type anywhere with local Faster Whisper.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to config.yaml (default: %%LOCALAPPDATA%%\\thai-voice-bridge\\config.yaml)",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("list-devices", help="List audio input devices")
    sub.add_parser("discover-cache", help="Show HF cache / model discovery (no download)")
    sub.add_parser("init-config", help="Create user config from example if missing")

    run_p = sub.add_parser("run", help="Run push-to-talk in console mode")
    run_p.add_argument("--no-lock", action="store_true", help="Skip single-instance lock")

    tray_p = sub.add_parser("tray", help="Run system tray application (recommended)")
    tray_p.add_argument("--no-lock", action="store_true", help="Skip single-instance lock")

    return parser


def cmd_list_devices() -> int:
    devices = list_input_devices()
    if not devices:
        print("No input devices found.")
        return 1
    for index, name in devices:
        print(f"[{index}] {name}")
    return 0


def cmd_discover_cache(config_path: Path | None) -> int:
    cfg = load_config(config_path)
    cache = apply_hf_cache_env(cfg)
    print(f"hf_cache_dir: {cache}")
    print(f"allow_model_download: {cfg.allow_model_download}")
    print(f"model: {cfg.model}")
    snap = discover_cached_model(cfg.model, cfg.hf_cache_dir)
    if snap:
        print(f"cached_snapshot: {snap}")
        print("status: READY (no download needed)")
        return 0
    print("cached_snapshot: (not found)")
    if cfg.allow_model_download:
        print("status: MISSING — download permitted by config")
    else:
        print("status: MISSING — download blocked (allow_model_download=false)")
    return 0


def cmd_init_config(config_path: Path | None) -> int:
    path = ensure_user_config(config_path or default_user_config_path())
    print(f"User config: {path}")
    return 0


def _acquire_lock(skip: bool) -> SingleInstanceLock | None:
    if skip:
        return None
    lock = SingleInstanceLock()
    lock.acquire()
    return lock


def cmd_run(config_path: Path | None, no_lock: bool) -> int:
    lock = _acquire_lock(no_lock)
    try:
        cfg = load_config(config_path)
        from thai_voice_bridge.app import VoiceBridgeApp

        app = VoiceBridgeApp(cfg)
        print(
            f"Ready. Hold [{cfg.hotkey.upper()}] to record. "
            f"auto_send={cfg.auto_send} model={cfg.model} device={cfg.device}"
        )
        app.preload_model()
        app.start_hotkey()
        app.wait()
        return 0
    finally:
        if lock:
            lock.release()


def cmd_tray(config_path: Path | None, no_lock: bool) -> int:
    lock = _acquire_lock(no_lock)
    try:
        cfg = load_config(config_path)
        ensure_user_config(default_user_config_path())
        from thai_voice_bridge.tray import run_tray

        return run_tray(cfg)
    finally:
        if lock:
            lock.release()


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    command = args.command or "tray"
    try:
        if command == "list-devices":
            return cmd_list_devices()
        if command == "discover-cache":
            return cmd_discover_cache(args.config)
        if command == "init-config":
            return cmd_init_config(args.config)
        if command == "run":
            return cmd_run(args.config, getattr(args, "no_lock", False))
        if command == "tray":
            return cmd_tray(args.config, getattr(args, "no_lock", False))
        parser.error(f"Unknown command: {command}")
        return 2
    except SingleInstanceError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
