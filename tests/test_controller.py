import queue
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from local_voice import asr_worker, controller as controller_module
from local_voice.config import Settings
from local_voice.controller import Controller, State

LOUD = np.random.default_rng(0).uniform(-0.5, 0.5, 16000).astype(np.float32)  # 1s, well above the silence threshold
SILENCE = np.zeros(16000, dtype=np.float32)


class FakeCaptureSession:
    """Replaces the real microphone-backed CaptureSession in these tests.
    Each instance pops the next (audio, limit_hit) pair from a shared script
    so tests can control exactly what each simulated recording "captured"."""

    script: list[tuple[np.ndarray, bool]] = []

    def __init__(self, device, recording_limit_seconds):
        self.device = device
        self.recording_limit_seconds = recording_limit_seconds

    def start(self) -> None:
        pass

    def stop(self):
        return FakeCaptureSession.script.pop(0)


@pytest.fixture
def ctrl(monkeypatch):
    monkeypatch.setattr(controller_module, "CaptureSession", FakeCaptureSession)
    clipboard_calls = []
    monkeypatch.setattr(controller_module.clipboard, "set_clipboard_text", lambda text: clipboard_calls.append(text))
    monkeypatch.setattr(controller_module.cleanup, "correct_grammar", lambda text: text)  # unused: mode stays "literal"

    settings = Settings(mode="literal", recording_limit_seconds=120)
    c = Controller(settings)
    # Real multiprocessing.Queue objects spawn a feeder thread on first put()
    # and register an atexit finalizer that joins it; since nothing in these
    # tests drains the queue (no real worker process), that join can hang
    # the whole test process at interpreter shutdown. Swap in plain
    # thread-safe queues, which these tests don't need to cross a process
    # boundary anyway.
    c._job_queue = queue.Queue()
    c._result_queue = queue.Queue()
    c.state = State.READY  # skip start(): no real worker process/model load in these tests
    c.clipboard_calls = clipboard_calls  # type: ignore[attr-defined]
    FakeCaptureSession.script = []
    yield c


def result_for(job_id: int, text: str = "hello") -> asr_worker.TranscribeResult:
    return asr_worker.TranscribeResult(job_id=job_id, text=text, duration_s=0.1)


def test_normal_recording_delivers_to_clipboard(ctrl):
    FakeCaptureSession.script = [(LOUD, False)]
    ctrl.on_ptt_down()
    assert ctrl.state is State.RECORDING
    ctrl.on_ptt_up()
    assert ctrl.state is State.TRANSCRIBING

    ctrl._handle_result_message(result_for(1, "hello world"))
    assert ctrl.state is State.READY
    assert ctrl.clipboard_calls == ["hello world"]


def test_silence_produces_no_clipboard_change(ctrl):
    FakeCaptureSession.script = [(SILENCE, False)]
    ctrl.on_ptt_down()
    ctrl.on_ptt_up()
    assert ctrl.state is State.READY  # discarded immediately, never reaches TRANSCRIBING
    assert ctrl.clipboard_calls == []


def test_cancel_during_recording_produces_no_clipboard_change(ctrl):
    FakeCaptureSession.script = [(LOUD, False)]
    ctrl.on_ptt_down()
    ctrl.on_cancel()
    assert ctrl.state is State.READY
    assert ctrl.clipboard_calls == []


def test_cancel_during_transcription_discards_late_result(ctrl):
    FakeCaptureSession.script = [(LOUD, False)]
    ctrl.on_ptt_down()
    ctrl.on_ptt_up()
    assert ctrl.state is State.TRANSCRIBING
    job_id = ctrl._current_job_id

    ctrl.on_cancel()
    assert ctrl.state is State.READY

    ctrl._handle_result_message(result_for(job_id, "should never appear"))
    assert ctrl.clipboard_calls == []  # late result for a cancelled job is discarded, not delivered


def test_auto_restart_keeps_both_chunks_alive_and_delivers_the_first_late(ctrl):
    """Simulates hitting the recording cap while the hotkey is still held:
    a new chunk starts recording while the previous chunk's transcription is
    still in flight. The first chunk's result must still be delivered when
    it arrives late, without being mistaken for stale/cancelled, and without
    clobbering the second chunk's now-current state."""
    FakeCaptureSession.script = [(LOUD, True), (LOUD, False)]  # first chunk hits the cap, second is a normal release

    ctrl.on_ptt_down()
    chunk1_id = ctrl._current_job_id

    # what the cap watchdog does when the key is still held at the cap:
    ctrl._finish_recording()
    assert ctrl.state is State.TRANSCRIBING
    ctrl._begin_recording(new_session=False)
    chunk2_id = ctrl._current_job_id
    assert chunk2_id != chunk1_id
    assert ctrl.state is State.RECORDING
    assert ctrl._session_job_ids == {chunk1_id, chunk2_id}

    # chunk 1's transcription finishes late, after chunk 2 has already taken over "current"
    ctrl._handle_result_message(result_for(chunk1_id, "first chunk text"))
    assert ctrl.clipboard_calls == ["first chunk text"]
    assert ctrl.state is State.RECORDING  # chunk 2 still owns the foreground state
    assert ctrl._current_job_id == chunk2_id

    ctrl.on_ptt_up()
    ctrl._handle_result_message(result_for(chunk2_id, "second chunk text"))
    assert ctrl.clipboard_calls == ["first chunk text", "second chunk text"]
    assert ctrl.state is State.READY


def test_cancel_cancels_every_chunk_in_the_session(ctrl):
    FakeCaptureSession.script = [(LOUD, True), (LOUD, False)]

    ctrl.on_ptt_down()
    chunk1_id = ctrl._current_job_id
    ctrl._finish_recording()
    ctrl._begin_recording(new_session=False)
    chunk2_id = ctrl._current_job_id

    ctrl.on_cancel()
    assert ctrl.state is State.READY

    ctrl._handle_result_message(result_for(chunk1_id, "chunk 1"))
    ctrl._handle_result_message(result_for(chunk2_id, "chunk 2"))
    assert ctrl.clipboard_calls == []  # both chunks belonged to the cancelled session
