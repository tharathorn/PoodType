# Thai Voice Bridge Safety Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Thai Voice Bridge stop, pause, recording, foreground paste, clipboard, and preload behavior fail closed.

**Architecture:** Add explicit cancellation and target validation at the app boundary, bounded recording in `Recorder`, fail-closed clipboard swapping, and preload gating in the tray. Preserve the existing local-only F8 pipeline.

**Tech Stack:** Python 3.10+, pytest, sounddevice, keyboard, pyperclip, pystray.

## Global Constraints

- Test first and verify each new test fails for the expected behavior.
- Do not install, register startup, push, deploy, or enable model downloads.
- Keep `auto_send: false` as the default.

---

### Task 1: Pause, exit, and stale hotkey cancellation

**Files:**
- Modify: `src/thai_voice_bridge/hotkey.py`
- Modify: `src/thai_voice_bridge/app.py`
- Test: `tests/test_hotkey.py`
- Test: `tests/test_app_safety.py`

- [ ] Write tests proving disable clears held state, pause cancels recording, and exit prevents an in-flight worker from pasting.
- [ ] Run the focused tests and verify they fail.
- [ ] Add key-state clearing and app cancellation generation checks.
- [ ] Run focused tests and verify they pass.

### Task 2: Stable foreground target

**Files:**
- Modify: `src/thai_voice_bridge/app.py`
- Test: `tests/test_app_safety.py`

- [ ] Write a test proving a foreground HWND change aborts paste.
- [ ] Run it and verify failure.
- [ ] Capture target at release and verify the same HWND immediately before paste.
- [ ] Run focused tests and verify pass.

### Task 3: Bound recording duration

**Files:**
- Modify: `src/thai_voice_bridge/config.py`
- Modify: `config.example.yaml`
- Modify: `src/thai_voice_bridge/audio.py`
- Modify: `src/thai_voice_bridge/app.py`
- Test: `tests/test_audio.py`
- Test: `tests/test_config.py`

- [ ] Write tests for a 60-second default and bounded over-limit recording.
- [ ] Run them and verify failure.
- [ ] Track maximum samples and reject over-limit capture without a WAV.
- [ ] Run focused tests and verify pass.

### Task 4: Clipboard and preload fail closed

**Files:**
- Modify: `src/thai_voice_bridge/paste.py`
- Modify: `src/thai_voice_bridge/tray.py`
- Test: `tests/test_clipboard.py`
- Test: `tests/test_tray.py`

- [ ] Write tests for clipboard-read failure, restore failure, and preload failure.
- [ ] Run them and verify failure.
- [ ] Raise `PasteError` instead of overwriting unknown clipboard state; start hotkey only after preload.
- [ ] Run focused tests and verify pass.

### Task 5: Verification and handoff

**Files:**
- Modify: `HANDOFF.md`
- Modify: `docs/MANUAL_SMOKE_CHECKLIST.md`

- [ ] Run `python -m pytest -q`.
- [ ] Run `python -m compileall -q src`.
- [ ] Confirm git status contains only intended files.
- [ ] Update handoff with fixes, test evidence, residual manual checks, and proposed Dev Orchestrator registration values.
