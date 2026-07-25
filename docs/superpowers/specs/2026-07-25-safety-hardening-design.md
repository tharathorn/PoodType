# Thai Voice Bridge Safety Hardening Design

## Goal

Make pause, exit, foreground targeting, recording duration, clipboard handling,
and model startup fail closed without changing the local-only dictation flow.

## Design

- `VoiceBridgeApp` owns a cancellation generation. Pause and exit invalidate
  work already transcribing; a worker checks cancellation before paste.
- Capture the foreground window when F8 is released. Paste only if the same
  nonzero HWND is still foreground after transcription.
- Pause and exit cancel any active recording. Disabling the hotkey also clears
  its key-down state so a later release cannot trigger stale work.
- `Recorder` has a 60-second default maximum. The callback bounds retained
  samples and marks the recording exceeded; `stop_to_wav` fails without writing.
- Clipboard capture is fail-closed: if prior text cannot be read, do not replace
  the clipboard. Restoration failure surfaces as `PasteError`.
- Tray hotkeys start only after model preload succeeds.

## Tests

Add focused tests for pause while recording, exit during transcription,
foreground changes, recording duration, disabled-key release, clipboard read
failure, restore failure, and preload failure. Run the full suite and compileall.

## Constraints

No network enablement, install, startup registration, push, deployment, or
changes outside this repository. `auto_send` remains false by default.
