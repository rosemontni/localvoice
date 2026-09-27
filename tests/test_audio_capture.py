import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from local_voice.audio_capture import _resample_linear, is_signal_present


def test_silence_is_rejected():
    assert not is_signal_present(np.zeros(16000, dtype=np.float32))


def test_too_short_is_rejected_even_if_loud():
    loud_but_brief = np.ones(100, dtype=np.float32)  # well under the 0.3s minimum
    assert not is_signal_present(loud_but_brief)


def test_loud_signal_of_sufficient_length_is_accepted():
    rng = np.random.default_rng(0)
    loud = rng.uniform(-0.5, 0.5, 16000).astype(np.float32)
    assert is_signal_present(loud)


def test_resample_linear_preserves_duration():
    original = np.linspace(-1, 1, 8000, dtype=np.float32)  # 0.5s @ 16 kHz
    resampled = _resample_linear(original, from_rate=16000, to_rate=48000)
    assert resampled.shape[0] == 24000  # 0.5s @ 48 kHz


def test_resample_linear_is_identity_when_rates_match():
    original = np.array([0.1, 0.2, 0.3], dtype=np.float32)
    assert np.array_equal(_resample_linear(original, 16000, 16000), original)
