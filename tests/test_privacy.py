"""Privacy sanitization helpers."""

from thai_voice_bridge.privacy import sanitize_text


def test_sanitize_redacts_secrets_and_truncates():
    text = "api_key=sk-secret-value " + ("ก" * 100)
    out = sanitize_text(text, max_chars=40)
    assert "sk-secret-value" not in out
    assert "REDACTED" in out
    assert "len=" in out
