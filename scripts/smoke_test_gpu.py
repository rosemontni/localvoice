"""M0/M1 smoke test: exercises config, silence rejection, and the real ASR
worker process (GPU) end-to-end on a synthesized WAV, without needing a live
microphone. Run with the local-voice env active:
    python scripts/smoke_test_gpu.py

test_en.wav was synthesized via Windows SAPI (System.Speech, Microsoft Zira
Desktop voice) from the sentence transcribed in the assertion below; it is a
substitute for a live recording, not a replacement for the Mandarin/mixed-
language human test the M1 exit gate still requires (see IMPLEMENTATION_PLAN.md).
"""
import multiprocessing as mp
import sys
import time
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import numpy as np

from local_voice import asr_worker
from local_voice.audio_capture import is_signal_present
from local_voice.config import Settings, load_settings, save_settings

WAV_PATH = Path(__file__).parent / "test_en.wav"


def load_wav_as_float32(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as wf:
        n_channels = wf.getnchannels()
        sample_rate = wf.getframerate()
        raw = wf.readframes(wf.getnframes())
    audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if n_channels > 1:
        audio = audio.reshape(-1, n_channels).mean(axis=1)
    if sample_rate != 16000:
        duration = audio.shape[0] / sample_rate
        target_len = int(round(duration * 16000))
        positions = np.linspace(0, audio.shape[0] - 1, num=target_len)
        audio = np.interp(positions, np.arange(audio.shape[0]), audio).astype(np.float32)
    return audio


def main() -> None:
    print("=== config round-trip ===")
    s = Settings(hotkey="f9")
    save_settings(s)
    reloaded = load_settings()
    assert reloaded.hotkey == "f9", reloaded
    print("OK:", reloaded)

    print("\n=== silence rejection ===")
    silence = np.zeros(16000, dtype=np.float32)
    assert not is_signal_present(silence)
    print("OK: pure silence correctly rejected")

    loud = (np.random.default_rng(0).uniform(-0.5, 0.5, 16000)).astype(np.float32)
    assert is_signal_present(loud)
    print("OK: loud noise correctly accepted as signal")

    print("\n=== ASR worker process: real GPU transcription of synthesized English speech ===")
    audio = load_wav_as_float32(WAV_PATH)
    print(f"loaded {audio.shape[0] / 16000:.2f}s of audio")

    job_queue: "mp.Queue" = mp.Queue()
    result_queue: "mp.Queue" = mp.Queue()
    proc = mp.Process(
        target=asr_worker.worker_main,
        args=(job_queue, result_queue, "large-v3-turbo", "cuda", "float16"),
        daemon=True,
    )
    t_start = time.monotonic()
    proc.start()

    msg = result_queue.get(timeout=120)
    assert msg[0] == asr_worker.READY, msg
    print(f"model loaded in {time.monotonic() - t_start:.1f}s")

    job_queue.put(asr_worker.TranscribeJob(job_id=1, audio=audio, language="auto"))
    result = result_queue.get(timeout=60)
    print(f"transcription ({result.duration_s:.2f}s): {result.text!r}")
    assert result.error is None, result.error
    assert result.text, "expected non-empty transcript"

    job_queue.put(asr_worker.SHUTDOWN)
    proc.join(timeout=5)
    print("\nALL SMOKE TESTS PASSED")


if __name__ == "__main__":
    mp.freeze_support()
    main()
