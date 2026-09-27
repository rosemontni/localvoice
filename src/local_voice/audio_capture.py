"""Bounded in-memory microphone capture for push-to-talk.

Capture callbacks only buffer samples, per docs/ARCHITECTURE.md: never run
inference or clipboard operations here.
"""

from __future__ import annotations

import logging
import threading

import numpy as np
import sounddevice as sd

logger = logging.getLogger("local_voice.audio")

TARGET_SAMPLE_RATE = 16000  # faster-whisper expects 16 kHz mono float32


class MicrophoneUnavailableError(RuntimeError):
    pass


class CaptureSession:
    """One push-to-talk recording: start() on key-down, stop() on key-up."""

    def __init__(self, device: str | int | None, recording_limit_seconds: int) -> None:
        self._device = None if device in (None, "default") else device
        self._max_frames = recording_limit_seconds * TARGET_SAMPLE_RATE
        self._frames: list[np.ndarray] = []
        self._lock = threading.Lock()
        self._limit_hit = False
        self._stream: sd.InputStream | None = None
        self.stream_samplerate = TARGET_SAMPLE_RATE

    def _callback(self, indata: np.ndarray, frames: int, time_info, status) -> None:  # noqa: ANN001
        if status:
            logger.warning("capture stream status flag: %s", status)
        with self._lock:
            if self._limit_hit:
                return
            total = sum(chunk.shape[0] for chunk in self._frames)
            if total >= self._max_frames:
                self._limit_hit = True
                return
            self._frames.append(indata.copy())

    def start(self) -> None:
        try:
            self._stream = sd.InputStream(
                samplerate=TARGET_SAMPLE_RATE,
                channels=1,
                dtype="float32",
                device=self._device,
                callback=self._callback,
            )
            self.stream_samplerate = TARGET_SAMPLE_RATE
            self._stream.start()
        except sd.PortAudioError:
            logger.info("device rejected 16 kHz capture, falling back to its default rate")
            device_info = sd.query_devices(self._device, "input")
            fallback_rate = int(device_info["default_samplerate"])
            self._stream = sd.InputStream(
                samplerate=fallback_rate,
                channels=1,
                dtype="float32",
                device=self._device,
                callback=self._callback,
            )
            self.stream_samplerate = fallback_rate
            self._stream.start()
        except Exception as exc:  # sounddevice raises varied errors for missing/denied devices
            raise MicrophoneUnavailableError(str(exc)) from exc

    def stop(self) -> tuple[np.ndarray, bool]:
        """Stop capture and return (mono float32 audio at 16 kHz, limit_hit)."""
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        with self._lock:
            frames = self._frames
            limit_hit = self._limit_hit
            self._frames = []
        if not frames:
            return np.zeros(0, dtype=np.float32), limit_hit
        audio = np.concatenate(frames, axis=0).reshape(-1)
        if self.stream_samplerate != TARGET_SAMPLE_RATE:
            audio = _resample_linear(audio, self.stream_samplerate, TARGET_SAMPLE_RATE)
        return audio, limit_hit


def _resample_linear(audio: np.ndarray, from_rate: int, to_rate: int) -> np.ndarray:
    if from_rate == to_rate or audio.size == 0:
        return audio
    duration = audio.shape[0] / from_rate
    target_len = max(1, int(round(duration * to_rate)))
    source_positions = np.linspace(0, audio.shape[0] - 1, num=target_len)
    return np.interp(source_positions, np.arange(audio.shape[0]), audio).astype(np.float32)


def is_signal_present(audio: np.ndarray, rms_threshold: float = 0.005, min_seconds: float = 0.3) -> bool:
    """Reject empty/near-silent captures so silence never reaches the clipboard."""
    if audio.size < int(min_seconds * TARGET_SAMPLE_RATE):
        return False
    rms = float(np.sqrt(np.mean(np.square(audio))))
    return rms >= rms_threshold
