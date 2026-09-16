"""Focused unit tests for offline spoken normalization of emails, URLs, and paths.

Ensures @, dots, slashes, and common TLDs expand into Thai-friendly spoken forms
purely offline, without audio hardware or network calls, and without altering
the existing terminal phonetic matcher.
"""

from __future__ import annotations

import pytest

from thai_voice_bridge.phrases import (
    canonicalize_token,
    match_terminal_command,
    normalize_pronunciation,
    tokenize_spoken,
)
from thai_voice_bridge.speak_paths import (
    COMMON_EXTENSIONS,
    COMMON_TLDS,
    DEFAULT_AT_SPOKEN,
    DEFAULT_BACKSLASH_SPOKEN,
    DEFAULT_COLON_SPOKEN,
    DEFAULT_DOT_SPOKEN,
    DEFAULT_DOUBLE_SLASH_SPOKEN,
    DEFAULT_SLASH_SPOKEN,
    DEFAULT_TILDE_SPOKEN,
    expand_at,
    expand_dots,
    expand_slashes,
    expand_spoken_forms,
    expand_tlds,
    is_email,
    is_filesystem_path,
    is_url,
    normalize_email,
    normalize_path,
    normalize_spoken_paths,
    normalize_url,
    speak_email,
    speak_filesystem_path,
    speak_path,
    speak_paths,
    speak_url,
)


# =====================================================================
# 1. Email Spoken Normalization
# =====================================================================


def test_speak_email_standard():
    assert speak_email("user@example.com") == "user แอท example ดอทคอม"
    assert speak_email("admin@test.org") == "admin แอท test ดอทออร์ก"
    assert speak_email("contact@company.net") == "contact แอท company ดอทเน็ต"
    assert speak_email("founder@startup.io") == "founder แอท startup ดอทไอโอ"
    assert speak_email("dev@engine.dev") == "dev แอท engine ดอทเดฟ"
    assert speak_email("ai@research.ai") == "ai แอท research ดอทเอไอ"


def test_speak_email_thai_cctlds():
    assert (
        speak_email("student@chula.ac.th")
        == "student แอท chula ดอทเอซีดอททีเอช"
    )
    assert (
        speak_email("dev@company.co.th")
        == "dev แอท company ดอทโคดอททีเอช"
    )
    assert (
        speak_email("officer@gov.go.th")
        == "officer แอท gov ดอทโกดอททีเอช"
    )
    assert (
        speak_email("charity@foundation.or.th")
        == "charity แอท foundation ดอทออร์ดอททีเอช"
    )
    assert (
        speak_email("person@thai.in.th")
        == "person แอท thai ดอทไอเอ็นดอททีเอช"
    )
    assert (
        speak_email("network@thai.net.th")
        == "network แอท thai ดอทเน็ตดอททีเอช"
    )
    assert (
        speak_email("direct@bangkok.th")
        == "direct แอท bangkok ดอททีเอช"
    )


def test_speak_email_with_dots_and_tags_in_local_part():
    assert (
        speak_email("john.doe@gmail.com")
        == "john ดอท doe แอท gmail ดอทคอม"
    )
    assert (
        speak_email("first.middle.last@domain.com")
        == "first ดอท middle ดอท last แอท domain ดอทคอม"
    )
    assert (
        speak_email("support+urgent@service.io")
        == "support+urgent แอท service ดอทไอโอ"
    )


def test_speak_email_with_subdomains():
    assert (
        speak_email("alerts@us-east.prod.aws.com")
        == "alerts แอท us-east ดอท prod ดอท aws ดอทคอม"
    )


def test_speak_email_custom_spoken_options():
    # Dot as "จุด"
    assert (
        speak_email("john.doe@corp.com", dot_spoken="จุด")
        == "john จุด doe แอท corp จุดคอม"
    )
    # Uncompounded TLD: "ดอท คอม"
    assert (
        speak_email("user@example.com", compound_tld=False)
        == "user แอท example ดอท คอม"
    )
    # Custom @ word
    assert (
        speak_email("user@example.com", at_spoken="แอต")
        == "user แอต example ดอทคอม"
    )


def test_speak_email_edge_cases():
    assert speak_email("") == ""
    assert speak_email(None) == ""
    assert speak_email("not-an-email") == "not-an-email"


# =====================================================================
# 2. URL Spoken Normalization
# =====================================================================


def test_speak_url_https_and_http():
    assert (
        speak_url("https://example.com")
        == "https โคลอน สแลช สแลช example ดอทคอม"
    )
    assert (
        speak_url("http://example.org")
        == "http โคลอน สแลช สแลช example ดอทออร์ก"
    )


def test_speak_url_with_paths():
    assert (
        speak_url("https://github.com/octocat/Hello-World")
        == "https โคลอน สแลช สแลช github ดอทคอม สแลช octocat สแลช Hello-World"
    )
    assert (
        speak_url("https://python.org/doc/index.html")
        == "https โคลอน สแลช สแลช python ดอทออร์ก สแลช doc สแลช index ดอท html"
    )


def test_speak_url_with_port_and_query():
    assert (
        speak_url("http://localhost:8080/api/v1")
        == "http โคลอน สแลช สแลช localhost โคลอน 8080 สแลช api สแลช v1"
    )
    assert (
        speak_url("https://example.com/search?q=thai+voice")
        == "https โคลอน สแลช สแลช example ดอทคอม สแลช search?q=thai+voice"
    )


def test_speak_url_www_and_thai_tlds():
    assert (
        speak_url("www.google.co.th")
        == "www ดอท google ดอทโคดอททีเอช"
    )
    assert (
        speak_url("https://portal.service.ac.th/login")
        == "https โคลอน สแลช สแลช portal ดอท service ดอทเอซีดอททีเอช สแลช login"
    )


def test_speak_url_ftp_and_file():
    assert (
        speak_url("ftp://ftp.is.co.za/linux")
        == "ftp โคลอน สแลช สแลช ftp ดอท is ดอทโคดอทแซดเอ สแลช linux"
        or "ftp โคลอน สแลช สแลช ftp ดอท is" in speak_url("ftp://ftp.is.co.za/linux")
    )
    assert (
        speak_url("file:///etc/hosts")
        == "file โคลอน สแลช สแลช สแลช etc สแลช hosts"
    )


def test_speak_url_custom_words():
    assert (
        speak_url("https://example.com/api", slash_spoken="ทับ", colon_spoken="สองจุด")
        == "https สองจุด สแลช สแลช example ดอทคอม ทับ api"
    )


def test_speak_url_edge_cases():
    assert speak_url("") == ""
    assert speak_url(None) == ""


# =====================================================================
# 3. Filesystem Path Spoken Normalization
# =====================================================================


def test_speak_filesystem_path_unix_absolute():
    assert (
        speak_filesystem_path("/var/log/syslog")
        == "สแลช var สแลช log สแลช syslog"
    )
    assert (
        speak_filesystem_path("/etc/nginx/nginx.conf")
        == "สแลช etc สแลช nginx สแลช nginx ดอท conf"
    )
    assert (
        speak_filesystem_path("/usr/local/bin/python3")
        == "สแลช usr สแลช local สแลช bin สแลช python3"
    )
    assert speak_filesystem_path("/") == "สแลช"


def test_speak_filesystem_path_unix_relative():
    assert (
        speak_filesystem_path("./src/thai_voice_bridge/speak_paths.py")
        == "ดอท สแลช src สแลช thai_voice_bridge สแลช speak_paths ดอท py"
    )
    assert (
        speak_filesystem_path("../config/app.yaml")
        == "ดอท ดอท สแลช config สแลช app ดอท yaml"
    )
    assert (
        speak_filesystem_path("../../scripts/deploy.sh")
        == "ดอท ดอท สแลช ดอท ดอท สแลช scripts สแลช deploy ดอท sh"
    )


def test_speak_filesystem_path_home_tilde():
    assert (
        speak_filesystem_path("~/.bashrc")
        == "ทิลดา สแลช ดอท bashrc"
    )
    assert (
        speak_filesystem_path("~/Documents/report.docx")
        == "ทิลดา สแลช Documents สแลช report ดอท docx"
    )
    assert (
        speak_filesystem_path("~/.bashrc", expand_tilde=False)
        == "~ สแลช ดอท bashrc"
    )


def test_speak_filesystem_path_windows_drive():
    assert (
        speak_filesystem_path(r"C:\Users\Admin\Documents\file.txt")
        == "C: แบ็กสแลช Users แบ็กสแลช Admin แบ็กสแลช Documents แบ็กสแลช file ดอท txt"
    )
    assert (
        speak_filesystem_path(r"D:\projects\code\app.py")
        == "D: แบ็กสแลช projects แบ็กสแลช code แบ็กสแลช app ดอท py"
    )
    assert (
        speak_filesystem_path("C:\\")
        == "C: แบ็กสแลช"
    )


def test_speak_filesystem_path_windows_forward_slash():
    assert (
        speak_filesystem_path("C:/Users/Admin/Desktop/data.csv")
        == "C: สแลช Users สแลช Admin สแลช Desktop สแลช data ดอท csv"
    )


def test_speak_filesystem_path_windows_unc():
    assert (
        speak_filesystem_path(r"\\server\share\data.csv")
        == "แบ็กสแลช แบ็กสแลช server แบ็กสแลช share แบ็กสแลช data ดอท csv"
    )


def test_speak_filesystem_path_standalone_files_and_dotfiles():
    assert speak_filesystem_path("main.py") == "main ดอท py"
    assert speak_filesystem_path("config.yaml") == "config ดอท yaml"
    assert speak_filesystem_path(".env") == "ดอท env"
    assert speak_filesystem_path(".gitignore") == "ดอท gitignore"
    assert speak_filesystem_path("archive.tar.gz") == "archive ดอท tar ดอท gz"


def test_speak_filesystem_path_custom_words():
    assert (
        speak_filesystem_path(
            "/var/log",
            slash_spoken="ทับ",
        )
        == "ทับ var ทับ log"
    )
    assert (
        speak_filesystem_path(
            "file.txt",
            dot_spoken="จุด",
        )
        == "file จุด txt"
    )


def test_speak_filesystem_path_edge_cases():
    assert speak_filesystem_path("") == ""
    assert speak_filesystem_path(None) == ""


# =====================================================================
# 4. Sentence-Level Normalization (speak_paths)
# =====================================================================


def test_speak_paths_embed_email_in_thai_sentence():
    sentence = "กรุณาส่งเอกสารมาที่ admin@example.com ด้วยครับ"
    expected = "กรุณาส่งเอกสารมาที่ admin แอท example ดอทคอม ด้วยครับ"
    assert speak_paths(sentence) == expected


def test_speak_paths_embed_url_in_thai_sentence():
    sentence = "สามารถเปิดดูได้ที่ https://www.google.co.th เลยครับ"
    expected = "สามารถเปิดดูได้ที่ https โคลอน สแลช สแลช www ดอท google ดอทโคดอททีเอช เลยครับ"
    assert speak_paths(sentence) == expected


def test_speak_paths_embed_unix_path_in_thai_sentence():
    sentence = "ตรวจสอบข้อผิดพลาดที่ /var/log/syslog แล้วรีสตาร์ต"
    expected = "ตรวจสอบข้อผิดพลาดที่ สแลช var สแลช log สแลช syslog แล้วรีสตาร์ต"
    assert speak_paths(sentence) == expected


def test_speak_paths_embed_windows_path_in_thai_sentence():
    sentence = r"ไฟล์อยู่ที่ C:\Users\Admin\config.json ครับ"
    expected = "ไฟล์อยู่ที่ C: แบ็กสแลช Users แบ็กสแลช Admin แบ็กสแลช config ดอท json ครับ"
    assert speak_paths(sentence) == expected


def test_speak_paths_embed_relative_path_and_dotfile():
    sentence = "รัน ./scripts/build_windows.ps1 แล้วแก้ .env"
    expected = "รัน ดอท สแลช scripts สแลช build_windows ดอท ps1 แล้วแก้ ดอท env"
    assert speak_paths(sentence) == expected


def test_speak_paths_multi_entity_sentence():
    sentence = (
        r"ส่งเมลแจ้ง team@company.co.th แล้วโหลดไฟล์จาก "
        r"https://files.company.co.th/setup.exe ไว้ใน D:\setup.exe"
    )
    out = speak_paths(sentence)
    assert "team แอท company ดอทโคดอททีเอช" in out
    assert "https โคลอน สแลช สแลช files ดอท company ดอทโคดอททีเอช สแลช setup ดอท exe" in out
    assert "D: แบ็กสแลช setup ดอท exe" in out


def test_speak_paths_preserves_sentence_boundary_punctuation():
    # Trailing period must not be eaten into the TLD or path
    assert (
        speak_paths("Contact info@example.com.")
        == "Contact info แอท example ดอทคอม."
    )
    assert (
        speak_paths("Visit https://example.org!")
        == "Visit https โคลอน สแลช สแลช example ดอทออร์ก!"
    )
    assert (
        speak_paths("Check (/var/log/syslog);")
        == "Check (สแลช var สแลช log สแลช syslog);"
    )


def test_speak_paths_plain_thai_and_prose_unchanged():
    plain = "สวัสดีครับ วันนี้อากาศดีมาก ไม่มีฝนตก"
    assert speak_paths(plain) == plain
    assert speak_paths("Python 3.12 release notes") == "Python 3.12 release notes"


def test_speak_paths_empty_and_whitespace():
    assert speak_paths("") == ""
    assert speak_paths("   ") == ""
    assert speak_paths(None) == ""


# =====================================================================
# 5. Standalone Expander Helpers & Classifiers
# =====================================================================


def test_expand_at():
    assert expand_at("user@host") == "user แอท host"
    assert expand_at("@admin") == "แอท admin"
    assert expand_at("") == ""


def test_expand_dots():
    assert expand_dots("a.b.c") == "a ดอท b ดอท c"
    assert expand_dots("file.txt", spoken="จุด") == "file จุด txt"
    assert expand_dots("") == ""


def test_expand_slashes():
    assert expand_slashes("a/b/c") == "a สแลช b สแลช c"
    assert expand_slashes(r"a\b\c") == "a แบ็กสแลช b แบ็กสแลช c"
    assert expand_slashes("a/b", slash_spoken="ทับ") == "a ทับ b"
    assert expand_slashes("") == ""


def test_expand_tlds():
    assert expand_tlds("test.com") == "test ดอทคอม"
    assert expand_tlds("chula.ac.th") == "chula ดอทเอซีดอททีเอช"
    assert expand_tlds("project.io") == "project ดอทไอโอ"
    assert expand_tlds("test.com", compound_tld=False) == "test ดอท คอม"
    assert expand_tlds("") == ""


def test_classifiers():
    assert is_email("alice@example.com")
    assert is_email("john.doe+work@corp.co.th")
    assert not is_email("not-an-email")
    assert not is_email("hello@")
    assert not is_email(None)

    assert is_url("https://example.com")
    assert is_url("http://localhost:3000")
    assert is_url("ftp://ftp.example.org")
    assert is_url("www.google.com")
    assert not is_url("not a url")
    assert not is_url(None)

    assert is_filesystem_path("/var/log")
    assert is_filesystem_path(r"C:\Windows")
    assert is_filesystem_path("./scripts/test.sh")
    assert is_filesystem_path("../config.yaml")
    assert is_filesystem_path("~/.bashrc")
    assert is_filesystem_path(r"\\nas\share")
    assert is_filesystem_path("app.py")
    assert is_filesystem_path(".env")
    assert not is_filesystem_path("regular text without paths")
    assert not is_filesystem_path(None)


def test_aliases_match_canonical_functions():
    assert normalize_spoken_paths is speak_paths
    assert expand_spoken_forms is speak_paths
    assert speak_path is speak_filesystem_path
    assert normalize_path is speak_filesystem_path
    assert normalize_email is speak_email
    assert normalize_url is speak_url


# =====================================================================
# 6. Offline & Zero Hardware / Network Dependencies
# =====================================================================


def test_offline_and_no_hardware_dependencies():
    """speak_paths must have zero imports of hardware audio, GUI, or network libraries."""
    import thai_voice_bridge.speak_paths as mod

    forbidden = (
        "sounddevice",
        "requests",
        "urllib",
        "httpx",
        "whisper",
        "pystray",
        "keyboard",
        "socket",
    )
    for lib in forbidden:
        assert lib not in mod.__dict__, f"Forbidden dependency {lib!r} found in speak_paths"


def test_speak_paths_is_deterministic():
    sample = "เปิดเว็บ https://portal.company.co.th หรือส่งเมลหา dev@test.com ที่ /var/log"
    res1 = speak_paths(sample)
    res2 = speak_paths(sample)
    res3 = speak_paths(sample)
    assert res1 == res2 == res3
    assert "portal ดอท company ดอทโคดอททีเอช" in res1
    assert "dev แอท test ดอทคอม" in res1
    assert "สแลช var สแลช log" in res1


# =====================================================================
# 7. Preserves Existing Phonetic Terminal Matcher
# =====================================================================


def test_phonetic_terminal_matcher_behavior_unchanged():
    """Ensure phrases.py terminal matcher behavior is 100% preserved."""
    assert match_terminal_command("กิต พุช") == "git push"
    assert match_terminal_command("กิต คอมมิท ขีด เอ็ม") == "git commit -m"
    assert match_terminal_command("กิต แอด ขีด ขีด ออล") == "git add --all"
    assert match_terminal_command("ด็อกเกอร์ รัน") == "docker run"
    assert match_terminal_command("เคลียร์ สกรีน") == "clear"

    # Terminal matcher preserves unknown CLI parameters/paths as raw tokens
    assert match_terminal_command("ซีดี /var/log") == "cd /var/log"
    assert match_terminal_command("ด็อกเกอร์ รัน nginx:latest") == "docker run nginx:latest"

    # In contrast, speak_paths explicitly expands paths for speech
    assert speak_paths("ซีดี /var/log") == "ซีดี สแลช var สแลช log"
