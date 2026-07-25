"""Dictionary / replacement profile tests."""

from __future__ import annotations

from thai_voice_bridge.config import AppConfig, AppProfile, Replacement, config_from_dict
from thai_voice_bridge.dictionary import (
    apply_replacements,
    is_bad_transcript,
    normalize_transcript,
    select_profile,
)
from thai_voice_bridge.foreground import ForegroundInfo


def test_apply_replacements_codex_and_tech_terms():
    reps = [
        Replacement(pattern=r"โคเด็ก|โคเดกซ์", replace="Codex"),
        Replacement(pattern=r"พาวเวอร์เชลล์", replace="PowerShell"),
        Replacement(pattern=r"เอพีไอ", replace="API"),
        Replacement(pattern=r"เอ็มซีพี", replace="MCP"),
    ]
    text = apply_replacements("ใช้ โคเด็ก กับ พาวเวอร์เชลล์ เรียก เอพีไอ ผ่าน เอ็มซีพี", reps)
    assert "Codex" in text
    assert "PowerShell" in text
    assert "API" in text
    assert "MCP" in text


def test_profile_extra_replacements_for_cursor():
    cfg = AppConfig(
        replacements=[Replacement(pattern=r"เคอร์เซอร์", replace="Cursor")],
        profiles={
            "cursor": AppProfile(
                name="cursor",
                match_process=["Cursor.exe"],
                extra_replacements=[
                    Replacement(pattern=r"คอมโพส", replace="Composer"),
                ],
            )
        },
    )
    fg = ForegroundInfo(
        hwnd=1, process_name="Cursor.exe", process_id=1, window_title="x"
    )
    assert select_profile(cfg, fg) is not None
    out = normalize_transcript("เปิด เคอร์เซอร์ แล้วใช้ คอมโพส", cfg, foreground=fg)
    assert "Cursor" in out
    assert "Composer" in out


def test_is_bad_transcript_empty_and_prompt_echo():
    assert is_bad_transcript("")
    assert is_bad_transcript("   ")
    assert is_bad_transcript("Codex, code", initial_prompt="Codex, code")
    assert not is_bad_transcript("สวัสดี Codex")


def test_example_dictionary_covers_required_terms():
    from pathlib import Path

    from thai_voice_bridge.config import load_config

    cfg = load_config(Path(__file__).resolve().parents[1] / "config.example.yaml")
    joined = " ".join(r.replace for r in cfg.replacements)
    for term in [
        "Codex",
        "Cursor",
        "Code Coach",
        "Dev Orchestrator",
        "Full Content",
        "HyperFrames",
        "HeyGen",
        "Python",
        "PowerShell",
        "GitHub",
        "API",
        "MCP",
    ]:
        assert term in joined
