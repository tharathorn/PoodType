# PoodType Wake-Word Mode Design

Date: 2026-07-26  
Status: approved for planning (owner review of this file required before implementation)

## Goal

Add an optional hands-free dictation mode that listens for a Thai wake phrase,
records speech, stops on an end phrase, then pastes the cleaned transcript —
without replacing the existing F8 push-to-talk path.

Users can switch modes from the tray. Default remains hotkey for backward
compatibility.

## Decisions locked with owner

| Topic | Choice |
| --- | --- |
| Mode UX | Tray switchable: `hotkey` \|\| `wake_word` (option C) |
| Start phrase | `เฮ้ พุดไทป์` |
| End phrase | `ส่งได้ พุดไทป์` |
| After end phrase | Paste only (`auto_send` stays false) |
| Phrase stripping | Remove start and end phrases from pasted text |
| Detection approach | Hybrid: VAD + Faster Whisper (approach 3) |
| Recording limit | **300 seconds (5 minutes)** for both F8 and wake-word |
| Limit exceeded | Beep → stop recording → **do not paste** |
| Start beep | Short beep when wake phrase accepted and recording begins |
| Stop beep | Short beep when end phrase accepted and recording stops (before transcription) |

## Non-goals (this phase)

- Separate wake-word engine (openWakeWord / Porcupine / etc.)
- Continuous full-Whisper on every audio frame while idle
- Auto-Enter / second end phrase for send
- Cloud APIs, telemetry, or new model downloads by default
- Changing public product name packaging beyond config/tray labels already shipped

## Architecture

```text
Tray Mode Switch
  ├─ hotkey     → HotkeyController (F8 hold/release) → existing flow
  └─ wake_word  → WakeWordListener
                    ├─ mic stream + VAD gate
                    ├─ short Whisper window → match start_phrase
                    ├─ Recorder (full utterance)
                    ├─ rolling/end-window Whisper → match end_phrase
                    ├─ strip phrases → confidence gate → paste
                    └─ return to listening
```

`VoiceBridgeApp` remains the orchestrator. Mode-specific listeners are pluggable
behind a small interface so Pause/Exit/cancellation generation stay shared.

## Components

### 1. Config

Extend `AppConfig` / `config.example.yaml`:

- `mode: hotkey | wake_word` (default `hotkey`)
- `max_recording_seconds: 300` (default raised from 60 for both modes)
- `wake_word.start_phrase` (default `เฮ้ พุดไทป์`)
- `wake_word.end_phrase` (default `ส่งได้ พุดไทป์`)
- `wake_word.vad_silence_seconds` (default `1.0`)
- `wake_word.match_tolerance` (default `0.8` — fuzzy normalize/match)

Legacy configs without `mode` keep hotkey behavior. Existing
`max_recording_seconds: 60` in a user file is respected until the user updates
it; `config.example.yaml` and packaged defaults use `300`.

### 2. Phrase matcher

Pure function(s):

- Normalize Thai transcript (reuse / extend dictionary normalization)
- Detect whether text contains start or end phrase within tolerance
- Strip leading start phrase and trailing end phrase for paste payload
- End phrase matching is active **only while recording**

### 3. VAD gate

Lightweight energy / silence detector over the mic stream:

- Idle: do not run Whisper until speech energy exceeds threshold
- After speech ends for `vad_silence_seconds`, close a candidate window for
  wake/end matching
- Fail closed on mic open failure (tray error state; hotkey mode still available)

Exact VAD library choice is an implementation detail; prefer no new paid
dependency. If an existing optional dependency already present can cover this,
prefer it; otherwise a simple RMS threshold + hangover is acceptable for v1.

### 4. WakeWordListener

States: `LISTENING` → `RECORDING` → `BUSY` → `LISTENING`

- LISTENING: VAD → short Whisper → if start match → beep(start) → RECORDING
- RECORDING: accumulate audio continuously; on each VAD silence gap, run a short
  Whisper pass over the recent tail and test for end phrase
- On end match: beep(stop) → stop recorder → BUSY → transcribe full utterance →
  strip → paste
- On max duration: beep(stop/error) → discard WAV/samples → no paste → LISTENING
- Does not enable F8 while active; HotkeyController remains disabled in this mode

### 5. Tray

- Menu items to select Mode: Hotkey (F8) / Wake word
- Switching modes cancels in-flight recording/transcription (increment work generation)
- Visual state continues via existing tray colors; listening-idle vs recording
  must remain distinguishable
- Pause/Resume disables/enables the active listener for the current mode

### 6. Shared safety (unchanged semantics)

- Clipboard fail-closed
- Foreground HWND capture at end-of-utterance (wake: when end phrase fires;
  hotkey: on F8 release) and paste only if still foreground
- Pause/Exit invalidate in-flight work
- `auto_send` default false

## Data flow (wake-word happy path)

1. User enables Wake word in tray.
2. Mic listens; VAD ignores silence.
3. User says start phrase → match → start beep → recording begins.
4. User dictates content.
5. User says end phrase → stop beep → recording ends.
6. Whisper transcribes full recording (or reuse already-decoded segments if
   implementation can do so without accuracy loss).
7. Strip start/end phrases; confidence gate; paste; clipboard restore.
8. Success beep (existing); return to listening.

## Error handling

| Case | Behavior |
| --- | --- |
| Mic unavailable | Error state + tray message; do not crash |
| Model preload failed | Same as today: no listener enabled |
| Ambiguous / no wake match | Stay listening; no beep |
| End phrase while not recording | Ignore |
| Empty / low-confidence after strip | No paste; error/busy feedback |
| Recording exceeds 300s | Stop, discard, no paste |
| Mode switch mid-record | Cancel, discard, switch |
| Foreground changed before paste | No paste |

## Testing

Unit / focused tests:

- Config defaults: mode hotkey, max 300 in example/defaults
- Phrase match + strip for start/end (including minor ASR variants where
  tolerance is defined)
- End phrase ignored when not recording
- Max duration discard path (shared recorder)
- Mode switch cancels recording / invalidates paste
- Wake listener state transitions with fakes (mic/VAD/Whisper mocked)

Manual smoke (owner):

- Tray switch hotkey ↔ wake-word
- Start phrase → dictate → end phrase → paste without Enter
- Phrases absent from pasted text
- 5-minute limit not required to wait full length in smoke; unit covers discard
- Pause during listening and during recording

## Performance / privacy notes

- Idle CPU should stay near F8-idle levels; Whisper runs only on VAD speech windows
- Still local-only; no network for wake detection
- Always-on mic in wake-word mode is explicit user choice via tray/config

## Implementation constraints

- Keep package local-first and offline-capable
- Prefer additive modules under `src/thai_voice_bridge/`
- Do not break existing hotkey tests
- No auto install to Windows Startup
- Do not push/release unless owner asks after implementation
