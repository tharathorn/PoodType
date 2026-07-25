import numpy as np
import pytest
import sounddevice as sd

from thai_voice_bridge.audio import AudioError, Recorder


def test_recording_limit_bounds_samples_and_rejects_wav():
    recorder = Recorder(samplerate=10, max_recording_seconds=1.0)
    recorder.recording = True

    with pytest.raises(sd.CallbackStop):
        recorder._callback(np.ones((15, 1), dtype=np.float32), 15, None, None)

    assert sum(len(chunk) for chunk in recorder._chunks) == 10
    with pytest.raises(AudioError, match="maximum duration"):
        recorder.stop_to_wav()
