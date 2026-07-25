# PoodType Privacy

PoodType is local-first software:

- Microphone audio is processed on the user's Windows computer.
- Transcription uses Faster Whisper locally; no transcription API key is used.
- Audio and full transcripts are not persisted by default.
- Temporary WAV files are deleted after processing by default.
- Clipboard contents are restored after paste; if the clipboard cannot be read,
  PoodType refuses to paste.
- PoodType does not include analytics, telemetry, advertising, or user accounts.

The offline distribution includes the `medium` model. A future online installer
may download the same model from Hugging Face only after an explicit user
action; model download does not require an API key.

Users can opt into audio/transcript persistence in their local config. Those
files remain the user's responsibility and are never uploaded by PoodType.
