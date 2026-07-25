# Security Policy

## Supported version

Security fixes are provided for the latest published PoodType release.

## Reporting

Do not publish sensitive vulnerability details in a public issue. Use GitHub's
private vulnerability reporting for `tharathorn/PoodType` when enabled, or
contact the repository owner privately.

## Security properties

- Local Faster Whisper inference; no transcription API key.
- Model download disabled by default in source configuration.
- No telemetry or remote command execution.
- Foreground-window validation before paste.
- Pause/Exit cancellation and bounded recording duration.
- Clipboard operations fail closed.
- `auto_send` defaults to false.

PoodType is not an operating-system sandbox. Anyone who can modify the installed
application, model files, configuration, or Python environment has the same
access as the current Windows user.
