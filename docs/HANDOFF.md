# HANDOFF — phrase streaming helpers (task worktree)

## 2026-09-07 — streaming phrase / token normalization

Added offline helpers in `src/thai_voice_bridge/phrases.py` (no mic / sounddevice):

- `normalize_token_stream` — join ASR chunks/tokens, collapse consecutive stutter
- `tokenize_phrase` / `streaming_text_window` — trailing token/char windows
- `StreamingPhraseWindow` — accumulate chunks and match wake/end on the tail
- `contains_phrase_low_latency` — phrase check against a bounded trailing window
- `_best_window_ratio` early-exits once `tolerance` is met (scan newest first)

Tests: `tests/test_phrases.py` (offline only).

Verify:

```powershell
python -m pytest -q tests/test_phrases.py
python -m compileall -q src/thai_voice_bridge/phrases.py
```

Not yet wired into `wake_listener.py`; integrate when ready for live latency wins.

Root session notes remain in repository-root `HANDOFF.md`.
