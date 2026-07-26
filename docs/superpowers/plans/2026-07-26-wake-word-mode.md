# PoodType Wake-Word Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a tray-switchable wake-word dictation mode (`เฮ้ พุดไทป์` → record → `ส่งได้ พุดไทป์` → paste) using VAD + Faster Whisper, while keeping F8 hotkey mode and raising the shared recording limit to 5 minutes.

**Architecture:** Keep `VoiceBridgeApp` as orchestrator. Add pure phrase matching, a small RMS VAD helper, and a `WakeWordListener` that owns the listening/recording loop. Tray selects `hotkey` vs `wake_word`; mode switches cancel in-flight work via the existing work-generation gate.

**Tech Stack:** Python 3.10+, pytest, sounddevice, numpy, faster-whisper, keyboard, pystray, existing PoodType safety helpers.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-26-wake-word-mode-design.md`
- Local-only; do not enable model download by default; no cloud wake APIs.
- Default mode remains `hotkey`; `auto_send` remains `false`.
- Default `max_recording_seconds` becomes `300` for both modes; over-limit discards and does not paste.
- Test-first for each task; run focused pytest before/after implementation.
- Do not install Startup, push a release, or change packaging assets unless required for config defaults.
- Start/stop beeps: start phrase → `feedback.start`; end phrase → `feedback.stop` before transcription.

## File map

| File | Responsibility |
| --- | --- |
| `src/thai_voice_bridge/config.py` | `mode`, `WakeWordConfig`, default max 300 |
| `config.example.yaml` | Document new keys / defaults |
| `src/thai_voice_bridge/phrases.py` | Normalize, match, strip start/end phrases |
| `src/thai_voice_bridge/vad.py` | RMS speech / silence detection |
| `src/thai_voice_bridge/wake_listener.py` | Wake listening / recording state machine |
| `src/thai_voice_bridge/app.py` | Mode start/stop, shared paste path, limit handling |
| `src/thai_voice_bridge/tray.py` | Mode menu + title showing active mode |
| `tests/test_config.py` | Config defaults / validation |
| `tests/test_phrases.py` | Match + strip |
| `tests/test_vad.py` | Speech vs silence |
| `tests/test_wake_listener.py` | Listener transitions with fakes |
| `tests/test_app_safety.py` / new wake app tests | Mode switch cancel, limit discard |
| `tests/test_tray.py` | Mode menu / boot path |
| `README.md`, `docs/MANUAL_SMOKE_CHECKLIST.md`, `HANDOFF.md` | Docs after behavior lands |

---

### Task 1: Config — mode, wake phrases, 300s limit

**Files:**
- Modify: `src/thai_voice_bridge/config.py`
- Modify: `config.example.yaml`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `WakeWordConfig(start_phrase: str, end_phrase: str, vad_silence_seconds: float, match_tolerance: float)`
- Produces: `AppConfig.mode: str` (`"hotkey"` \| `"wake_word"`)
- Produces: `AppConfig.max_recording_seconds: float` default `300.0`
- Produces: `AppConfig.wake_word: WakeWordConfig`

- [ ] **Step 1: Write the failing tests**

```python
def test_config_defaults_include_wake_word_mode_and_five_minute_limit():
    cfg = config_from_dict({})
    assert cfg.mode == "hotkey"
    assert cfg.max_recording_seconds == 300.0
    assert cfg.wake_word.start_phrase == "เฮ้ พุดไทป์"
    assert cfg.wake_word.end_phrase == "ส่งได้ พุดไทป์"
    assert cfg.auto_send is False


def test_mode_must_be_hotkey_or_wake_word():
    with pytest.raises(ConfigError):
        config_from_dict({"mode": "always_on"})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m pytest -q tests/test_config.py::test_config_defaults_include_wake_word_mode_and_five_minute_limit tests/test_config.py::test_mode_must_be_hotkey_or_wake_word`
Expected: FAIL (missing fields / still default 60 / no mode validation)

- [ ] **Step 3: Implement minimal config**

Add:

```python
@dataclass
class WakeWordConfig:
    start_phrase: str = "เฮ้ พุดไทป์"
    end_phrase: str = "ส่งได้ พุดไทป์"
    vad_silence_seconds: float = 1.0
    match_tolerance: float = 0.8
```

On `AppConfig`:
- `mode: str = "hotkey"`
- `max_recording_seconds: float = 300.0`
- `wake_word: WakeWordConfig = field(default_factory=WakeWordConfig)`

In `config_from_dict`, parse nested `wake_word`, validate `mode in {"hotkey", "wake_word"}`, keep `max_recording_seconds > 0`.

Update `config.example.yaml` accordingly (`max_recording_seconds: 300`, `mode`, `wake_word` block).

- [ ] **Step 4: Run tests to verify they pass**

Run: `.\.venv\Scripts\python.exe -m pytest -q tests/test_config.py`
Expected: PASS (update any older assertions that still expect `60.0`)

- [ ] **Step 5: Commit**

```bash
git add src/thai_voice_bridge/config.py config.example.yaml tests/test_config.py
git commit -m "feat: add wake-word config and 5-minute recording default"
```

---

### Task 2: Phrase match and strip

**Files:**
- Create: `src/thai_voice_bridge/phrases.py`
- Test: `tests/test_phrases.py`

**Interfaces:**
- Consumes: start/end phrase strings + tolerance float
- Produces:
  - `normalize_phrase_text(text: str) -> str`
  - `contains_phrase(text: str, phrase: str, *, tolerance: float) -> bool`
  - `strip_command_phrases(text: str, *, start_phrase: str, end_phrase: str, tolerance: float) -> str`

- [ ] **Step 1: Write the failing tests**

```python
from thai_voice_bridge.phrases import contains_phrase, strip_command_phrases

START = "เฮ้ พุดไทป์"
END = "ส่งได้ พุดไทป์"

def test_detects_start_and_end_phrases():
    assert contains_phrase("เฮ้ พุดไทป์", START, tolerance=0.8)
    assert contains_phrase("ครับ ส่งได้ พุดไทป์", END, tolerance=0.8)
    assert not contains_phrase("พรุ่งนี้ประชุม", END, tolerance=0.8)


def test_strips_start_and_end_for_paste_payload():
    text = "เฮ้ พุดไทป์ พรุ่งนี้ประชุม 10 โมง ส่งได้ พุดไทป์"
    assert strip_command_phrases(
        text, start_phrase=START, end_phrase=END, tolerance=0.8
    ) == "พรุ่งนี้ประชุม 10 โมง"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m pytest -q tests/test_phrases.py`
Expected: FAIL ImportError / missing module

- [ ] **Step 3: Implement `phrases.py`**

Minimal approach:
- Collapse whitespace
- Compare with normalized forms (strip punctuation spaces)
- `contains_phrase`: true if normalized phrase is a substring, or SequenceMatcher ratio of best window ≥ tolerance
- `strip_command_phrases`: remove one leading start match and one trailing end match; strip leftover whitespace

- [ ] **Step 4: Run tests to verify they pass**

Run: `.\.venv\Scripts\python.exe -m pytest -q tests/test_phrases.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/thai_voice_bridge/phrases.py tests/test_phrases.py
git commit -m "feat: add wake/end phrase matching and stripping"
```

---

### Task 3: RMS VAD helper

**Files:**
- Create: `src/thai_voice_bridge/vad.py`
- Test: `tests/test_vad.py`

**Interfaces:**
- Produces: `class EnergyVad` with
  - `__init__(self, *, samplerate: int, silence_seconds: float, speech_rms: float = 0.02)`
  - `update(self, frame: np.ndarray) -> Literal["speech", "silence", "silence_complete"]`
  - `reset(self) -> None`

- [ ] **Step 1: Write the failing tests**

```python
import numpy as np
from thai_voice_bridge.vad import EnergyVad

def test_silence_complete_after_configured_hangover():
    vad = EnergyVad(samplerate=16000, silence_seconds=0.1, speech_rms=0.02)
    speech = np.full(1600, 0.2, dtype=np.float32)
    quiet = np.zeros(1600, dtype=np.float32)
    assert vad.update(speech) == "speech"
    # enough quiet frames to exceed 0.1s
    states = [vad.update(quiet) for _ in range(2)]
    assert "silence_complete" in states
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest -q tests/test_vad.py`
Expected: FAIL ImportError

- [ ] **Step 3: Implement RMS VAD**

Track consecutive silent samples after speech has been seen; emit `silence_complete` once silent duration ≥ `silence_seconds`, then reset speech latch as needed for the next utterance.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.\.venv\Scripts\python.exe -m pytest -q tests/test_vad.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/thai_voice_bridge/vad.py tests/test_vad.py
git commit -m "feat: add energy VAD for wake-word listening"
```

---

### Task 4: WakeWordListener state machine (faked I/O)

**Files:**
- Create: `src/thai_voice_bridge/wake_listener.py`
- Test: `tests/test_wake_listener.py`

**Interfaces:**
- Consumes: `AppConfig`, callbacks:
  - `on_utterance(wav_path: Path, expected_foreground, work_generation: int) -> None`
  - `transcribe_window(audio: np.ndarray) -> str` (injected for tests)
- Produces: `class WakeWordListener`
  - `start() -> None`
  - `stop() -> None`
  - `disable() -> None` / `enable() -> None` for Pause/Resume parity

Behavior to encode:
1. Listening until start phrase matched → beep start (via injected feedback or app callback)
2. Recording until end phrase matched on VAD silence gap → beep stop → hand utterance to callback
3. Ignore end phrase while not recording
4. If recording exceeds `max_recording_seconds`, discard and return to listening without callback paste path

- [ ] **Step 1: Write the failing tests** with a fake clock/audio pump feeding numpy frames and a fake `transcribe_window` returning scripted strings.

```python
def test_start_phrase_enters_recording_and_end_phrase_emits_utterance(tmp_path):
    # pump frames → fake ASR returns start → then content → then end
    # assert one on_utterance call and no paste of command phrases here
    ...


def test_end_phrase_ignored_while_listening():
    ...


def test_max_duration_discards_without_utterance_callback():
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m pytest -q tests/test_wake_listener.py`
Expected: FAIL ImportError / missing class

- [ ] **Step 3: Implement listener**

Keep mic open via sounddevice InputStream callback collecting float32 mono frames. Use `EnergyVad` for speech windows. For listening mode, on `silence_complete` run `transcribe_window` on the speech buffer. For recording mode, keep all samples; on silence gaps, check recent tail for end phrase; on match, write WAV with existing `write_wav` / `unique_temp_wav` helpers and invoke `on_utterance`.

Inject `transcribe_window` in production from a thin wrapper around `WhisperEngine` operating on an in-memory WAV or temp WAV.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.\.venv\Scripts\python.exe -m pytest -q tests/test_wake_listener.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/thai_voice_bridge/wake_listener.py tests/test_wake_listener.py
git commit -m "feat: add wake-word listener state machine"
```

---

### Task 5: Wire VoiceBridgeApp modes + shared paste/safety

**Files:**
- Modify: `src/thai_voice_bridge/app.py`
- Modify: `src/thai_voice_bridge/audio.py` only if constructor default still hardcodes 60 in tests unexpectedly
- Test: `tests/test_app_safety.py` (extend) or `tests/test_app_wake_mode.py`

**Interfaces:**
- Produces on `VoiceBridgeApp`:
  - `start_input() -> None` — starts hotkey or wake listener from `config.mode`
  - `set_mode(mode: str) -> None` — cancel work, stop other listener, start new mode
  - Reuse `_transcribe_and_paste` after stripping phrases for wake path

- [ ] **Step 1: Write failing tests**

```python
def test_set_mode_to_wake_word_disables_hotkey_and_cancels_recording(monkeypatch):
    ...


def test_wake_utterance_strips_phrases_before_paste(monkeypatch):
    ...
```

Also update any test that assumed default max `60.0` if still present.

- [ ] **Step 2: Run focused tests — expect FAIL**

- [ ] **Step 3: Implement wiring**

- `start_hotkey()` remains for hotkey mode
- Add wake path calling `WakeWordListener`
- `pause_listening` / `stop` disable whichever listener is active and bump `_work_generation`
- On wake utterance: capture foreground at stop beep moment; strip phrases; call existing confidence/paste pipeline
- Over-limit already handled inside recorder/listener: ensure app does not paste

- [ ] **Step 4: Run focused + full suite subset**

Run: `.\.venv\Scripts\python.exe -m pytest -q tests/test_app_safety.py tests/test_app_wake_mode.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/thai_voice_bridge/app.py tests/test_app_safety.py tests/test_app_wake_mode.py
git commit -m "feat: wire wake-word mode into VoiceBridgeApp"
```

---

### Task 6: Tray mode switch UI

**Files:**
- Modify: `src/thai_voice_bridge/tray.py`
- Test: `tests/test_tray.py`

**Interfaces:**
- Tray menu radio-style items: `Mode: Hotkey (F8)` and `Mode: Wake word`
- Title includes mode, e.g. `PoodType [idle] — wake_word` or `… — F8`
- `_boot` calls `app.start_input()` instead of only `start_hotkey()`
- Mode change persists by rewriting user config `mode:` key without clobbering other settings (load YAML → set mode → dump), or set in-memory only for session if rewrite is risky — prefer in-memory + write `mode` field only via round-trip of existing user YAML

- [ ] **Step 1: Write failing test** that TrayApplication exposes mode switch callable and boot uses `start_input`.

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement menu + boot**

- [ ] **Step 4: Run `tests/test_tray.py` — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add src/thai_voice_bridge/tray.py tests/test_tray.py
git commit -m "feat: add tray switch for hotkey vs wake-word mode"
```

---

### Task 7: Docs, smoke checklist, full verification

**Files:**
- Modify: `README.md`
- Modify: `docs/MANUAL_SMOKE_CHECKLIST.md`
- Modify: `HANDOFF.md`

- [ ] **Step 1: Document** wake phrases, tray mode switch, 5-minute limit, paste-only end behavior

- [ ] **Step 2: Add manual checklist items**
  - Switch to wake-word
  - Say start → dictate → end → paste without Enter
  - Confirm phrases stripped
  - Switch back to F8
  - Pause while listening

- [ ] **Step 3: Full verify**

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m compileall -q src
```

Expected: all tests PASS; compileall exit 0

- [ ] **Step 4: Commit**

```bash
git add README.md docs/MANUAL_SMOKE_CHECKLIST.md HANDOFF.md
git commit -m "docs: document wake-word mode and 5-minute limit"
```

- [ ] **Step 5: Stop for owner manual smoke** — do not push/release unless owner asks

---

## Spec coverage checklist

| Spec requirement | Task |
| --- | --- |
| Tray switch hotkey / wake_word | 6 |
| Start `เฮ้ พุดไทป์` / end `ส่งได้ พุดไทป์` | 1, 2, 4 |
| Paste only, no Enter | 5 (existing auto_send false) |
| Strip phrases | 2, 5 |
| VAD + Whisper hybrid | 3, 4 |
| Start + stop beeps | 4, 5 |
| 300s both modes; discard no paste | 1, 4, 5 |
| Pause/Exit cancel | 5 |
| Foreground fail-closed | 5 (reuse) |
| Default mode hotkey | 1 |
| Docs / smoke | 7 |

## Self-review notes

- No TBD placeholders left in tasks.
- End-phrase detection uses VAD silence gaps (matches locked spec).
- Default max duration change may break older tests asserting `60.0` — Task 1 explicitly updates them.
