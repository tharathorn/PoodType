"""Dictionary / replacement profile and phonetic matcher tests."""

from __future__ import annotations

import pytest

from thai_voice_bridge.config import AppConfig, AppProfile, Replacement, config_from_dict
from thai_voice_bridge.dictionary import (
    apply_replacements,
    is_bad_transcript,
    normalize_transcript,
    select_profile,
)
from thai_voice_bridge.foreground import ForegroundInfo
from thai_voice_bridge.phrases import (
    PRONUNCIATION_ALIASES,
    apply_tech_vocabulary,
    canonicalize_token,
    match_terminal_command,
    normalize_pronunciation,
    tokenize_spoken,
)


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


# --- Offline Thai technical vocabulary / terminal phonetic matcher ---


def test_normalize_pronunciation_collapses_space_case_and_punct():
    assert normalize_pronunciation("  กิต   พุช  ") == "กิต พุช"
    assert normalize_pronunciation("Git Push!") == "git push"
    assert normalize_pronunciation("NPM, run-dev.") == "npm run-dev"
    assert normalize_pronunciation("") == ""
    assert normalize_pronunciation(None) == ""  # type: ignore[arg-type]


def test_tokenize_spoken_splits_on_whitespace():
    assert tokenize_spoken("  กิต  พุช ") == ("กิต", "พุช")
    assert tokenize_spoken("") == ()


def test_canonicalize_token_maps_phonetic_aliases():
    assert canonicalize_token("กิต") == "git"
    assert canonicalize_token("ด็อกเกอร์") == "docker"
    assert canonicalize_token("เอ็นพีเอ็ม") == "npm"
    assert canonicalize_token("ไพธอน") == "python"
    assert canonicalize_token("ไพทอน") == "python"
    assert canonicalize_token("ซีดี") == "cd"
    assert canonicalize_token("คอนฟิก") == "config"
    assert canonicalize_token("Git") == "git"
    assert canonicalize_token("unknown_xyz") == "unknown_xyz"


def test_pronunciation_aliases_cover_core_cli_verbs():
    for spoken, expected in [
        ("พุช", "push"),
        ("พูล", "pull"),
        ("คอมมิท", "commit"),
        ("สเตตัส", "status"),
        ("รัน", "run"),
        ("บิลด์", "build"),
        ("เคลียร์", "clear"),
        ("สกรีน", "screen"),
        ("เดฟ", "dev"),
        ("อินสตอล", "install"),
    ]:
        assert canonicalize_token(spoken) == expected
        assert spoken in PRONUNCIATION_ALIASES or normalize_pronunciation(spoken) in PRONUNCIATION_ALIASES


@pytest.mark.parametrize(
    "spoken,expected",
    [
        ("กิต พุช", "git push"),
        ("กิต คอมมิท", "git commit"),
        ("กิต สเตตัส", "git status"),
        ("ด็อกเกอร์ รัน", "docker run"),
        ("ด็อกเกอร์ บิลด์", "docker build"),
        ("เอ็นพีเอ็ม รัน เดฟ", "npm run dev"),
        ("ไพธอน", "python"),
        ("คอนฟิก", "config"),
        ("ซีดี", "cd"),
        ("เคลียร์ สกรีน", "clear"),
        ("กิต พูล", "git pull"),
        ("npm run DEV", "npm run dev"),
    ],
)
def test_match_terminal_command_exact_phrases(spoken: str, expected: str):
    assert match_terminal_command(spoken) == expected


def test_match_terminal_command_flag_aliases():
    assert match_terminal_command("กิต คอมมิท ขีด เอ็ม") == "git commit -m"
    assert match_terminal_command("กิต แอด ขีด ขีด ออล") == "git add --all"
    assert match_terminal_command("กิต ล็อก ขีด พี") == "git log -p"


def test_match_terminal_command_preserves_unknown_parameters():
    assert (
        match_terminal_command("กิต คอมมิท ขีด เอ็ม แก้บั๊กล็อกอิน")
        == "git commit -m แก้บั๊กล็อกอิน"
    )
    assert match_terminal_command("ซีดี /var/log") == "cd /var/log"
    assert match_terminal_command("ด็อกเกอร์ รัน nginx:latest") == "docker run nginx:latest"


def test_match_terminal_command_handles_whitespace_and_punctuation_noise():
    assert match_terminal_command("  กิต,  พุช!! ") == "git push"
    assert match_terminal_command("ด็อกเกอร์…บิลด์") == "docker build"
    assert match_terminal_command("เอ็นพีเอ็ม/รัน/เดฟ") == "npm run dev"


def test_apply_tech_vocabulary_in_free_transcript():
    out = apply_tech_vocabulary("เปิด เคอร์เซอร์ แล้วรัน เอ็นพีเอ็ม รัน เดฟ")
    assert "Cursor" in out
    assert "npm run dev" in out
    out2 = apply_tech_vocabulary("ใช้ ไพทอน กับ พาวเวอร์เชลล์ เรียก เอพีไอ")
    assert "Python" in out2
    assert "PowerShell" in out2
    assert "API" in out2


def test_apply_tech_vocabulary_is_deterministic_and_offline():
    sample = "กิต พุช แล้ว ด็อกเกอร์ บิลด์"
    assert apply_tech_vocabulary(sample) == apply_tech_vocabulary(sample)
    assert match_terminal_command(sample) == "git push แล้ว docker build"
    # Module must not depend on network/audio stacks at import time.
    import thai_voice_bridge.phrases as phrases_mod

    for forbidden in ("sounddevice", "requests", "urllib", "whisper", "httpx"):
        assert forbidden not in phrases_mod.__dict__


def test_config_from_dict_still_loads_when_phrases_imported():
    # Guard: phrases import must not break config helpers used by replacements.
    cfg = config_from_dict(
        {
            "dictionary": {
                "replacements": [{"pattern": "กิต", "replace": "git"}],
            }
        }
    )
    assert cfg.replacements[0].replace == "git"
