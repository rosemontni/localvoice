"""State machine tying capture, ASR worker, and clipboard delivery together.

Pipeline and states follow docs/ARCHITECTURE.md:
Starting -> Loading -> Ready -> Recording -> Transcribing -> Delivering -> Ready

Cancellation invalidates job ids; any late ASR result for a cancelled job_id
is discarded rather than delivered, per the same doc.

Session context: the last few delivered dictations are kept in memory
(`_recent_context`, in-memory only, never persisted or logged) and passed to
the grammar-cleanup step as reference context, so it can use recurring
names/topics from earlier in the session to disambiguate the current one --
the same idea Typeless uses server-side with much larger context, applied
locally at a much smaller scale.

The grammar-cleanup backend (settings.cleanup_backend) is "local" (Ollama,
on-device) by default; "cloud" (cloud_cleanup.py, Anthropic API) sends the
dictated text -- never audio -- to a frontier model instead, opt-in only.
See docs/DECISIONS_AND_RISKS.md, 2026-09-28.

Cross-session memory (memory.py) extends this across restarts: a bounded,
abstracted list of standing facts (names/recurring terms, not raw
transcripts) persisted to disk, on by default (settings.persistent_context).
See scripts/manage_memory.py to inspect or clear it, and
docs/DECISIONS_AND_RISKS.md for the privacy trade-off this represents.

Recording-cap handling: if the hotkey is still held when the recording hits
`recording_limit_seconds`, the controller auto-restarts a new chunk rather
than silently truncating (a forgotten held key must not lose audio). This
means more than one job can legitimately be in flight for one continuous
hold: the just-finished chunk may still be transcribing while the next
chunk is already recording. `_current_job_id` therefore only tracks which
job owns the *foreground* state (RECORDING/TRANSCRIBING) right now; a
result for an older chunk in the same session is still delivered (cleaned
up and copied to the clipboard) when it arrives, it just does not touch
`state`/`_current_job_id` since a newer chunk already owns those. All
chunks in one continuous hold share a session id set so Esc cancels the
whole held session, not just the chunk currently recording.
"""

from __future__ import annotations

import logging
import multiprocessing as mp
import threading
import time
from collections import deque
from enum import Enum, auto
from typing import Callable

from . import asr_worker, clipboard, cleanup, cloud_cleanup, memory, paste
from .audio_capture import CaptureSession, MicrophoneUnavailableError, is_signal_present
from .config import Settings

logger = logging.getLogger("local_voice.controller")

MAX_AUTO_RESTART_CHUNKS = 10  # ~20 minutes at the 120s default cap; guards against a truly stuck key
SESSION_CONTEXT_SIZE = 3  # how many recent delivered dictations are kept as cleanup context; in-memory only, never persisted


class State(Enum):
    STARTING = auto()
    LOADING = auto()
    READY = auto()
    RECORDING = auto()
    TRANSCRIBING = auto()
    UNAVAILABLE = auto()


class Controller:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._lock = threading.RLock()
        self.state = State.STARTING
        self.unavailable_reason: str | None = None

        self._job_counter = 0
        self._current_job_id: int | None = None  # job owning the foreground RECORDING/TRANSCRIBING state
        self._session_job_ids: set[int] = set()  # all chunk job ids from the current continuous hotkey hold
        self._chunk_count_in_session = 0
        self._cancelled_job_ids: set[int] = set()
        self._release_time_by_job: dict[int, float] = {}
        self._foreground_target_by_job: dict[int, paste.ForegroundTarget | None] = {}

        self._capture: CaptureSession | None = None
        self._recording_started_at: float | None = None
        self._ptt_held_probe: Callable[[], bool] | None = None
        self._recent_context: deque[str] = deque(maxlen=SESSION_CONTEXT_SIZE)  # in-memory only; cleared on restart

        self._job_queue: "mp.Queue" = mp.Queue()
        self._result_queue: "mp.Queue" = mp.Queue()
        self._worker_process: mp.Process | None = None
        self._result_thread: threading.Thread | None = None
        self._cap_watchdog_thread: threading.Thread | None = None
        self._shutdown_event = threading.Event()

    def set_ptt_held_probe(self, probe: Callable[[], bool]) -> None:
        """Wired to HotkeyListener.is_ptt_held so the cap watchdog can tell
        whether to auto-restart (key still down) or just stop (key released
        right as the cap was hit)."""
        self._ptt_held_probe = probe

    # -- lifecycle -----------------------------------------------------

    def start(self) -> None:
        with self._lock:
            self.state = State.LOADING
        self._worker_process = mp.Process(
            target=asr_worker.worker_main,
            args=(self._job_queue, self._result_queue, self.settings.model_size, self.settings.device, self.settings.compute_type),
            daemon=True,
        )
        self._worker_process.start()
        self._result_thread = threading.Thread(target=self._result_loop, daemon=True)
        self._result_thread.start()
        self._cap_watchdog_thread = threading.Thread(target=self._cap_watchdog_loop, daemon=True)
        self._cap_watchdog_thread.start()
        logger.info("controller starting; loading %s on %s/%s", self.settings.model_size, self.settings.device, self.settings.compute_type)

    def shutdown(self) -> None:
        self._shutdown_event.set()
        with self._lock:
            if self._capture is not None:
                try:
                    self._capture.stop()
                except Exception:
                    pass
                self._capture = None
        try:
            self._job_queue.put(asr_worker.SHUTDOWN)
        except Exception:
            pass
        if self._worker_process is not None:
            self._worker_process.join(timeout=5)
            if self._worker_process.is_alive():
                logger.warning("ASR worker did not exit cleanly; terminating")
                self._worker_process.terminate()
        logger.info("controller shut down")

    # -- recording lifecycle (shared by hotkey callbacks and the cap watchdog) --

    def _begin_recording(self, new_session: bool) -> None:
        """Caller must hold self._lock."""
        self._job_counter += 1
        job_id = self._job_counter
        if new_session:
            self._session_job_ids = {job_id}
            self._chunk_count_in_session = 1
        else:
            self._session_job_ids.add(job_id)
            self._chunk_count_in_session += 1
        try:
            capture = CaptureSession(self.settings.microphone, self.settings.recording_limit_seconds)
            capture.start()
        except MicrophoneUnavailableError as exc:
            logger.error("microphone unavailable: %s", exc)
            self._session_job_ids.discard(job_id)
            return
        self._capture = capture
        self._current_job_id = job_id
        self._foreground_target_by_job[job_id] = paste.get_foreground_target()
        self._recording_started_at = time.monotonic()
        self.state = State.RECORDING
        tag = "" if new_session else " [auto-restarted chunk after hitting the recording cap]"
        logger.info("recording started (job %d)%s", job_id, tag)

    def _finish_recording(self) -> None:
        """Stop the active capture and submit its audio as a job, if any is
        active. Caller must hold self._lock."""
        if self._capture is None:
            return
        job_id = self._current_job_id
        audio, limit_hit = self._capture.stop()
        self._capture = None
        self._recording_started_at = None
        release_time = time.monotonic()
        if limit_hit:
            logger.warning("job %d hit the %ds recording cap", job_id, self.settings.recording_limit_seconds)

        if not is_signal_present(audio):
            logger.info("job %d discarded: silence or too short, no clipboard change", job_id)
            self.state = State.READY
            self._current_job_id = None
            self._session_job_ids.discard(job_id)
            self._foreground_target_by_job.pop(job_id, None)
            return

        self._release_time_by_job[job_id] = release_time
        self.state = State.TRANSCRIBING
        logger.info("job %d transcribing (%.1fs audio)", job_id, audio.shape[0] / 16000)
        hotwords = " ".join(self.settings.vocabulary) if self.settings.vocabulary else None
        self._job_queue.put(asr_worker.TranscribeJob(job_id=job_id, audio=audio, language=self.settings.language, hotwords=hotwords))

    # -- hotkey callbacks ------------------------------------------------

    def on_ptt_down(self) -> None:
        with self._lock:
            if self.state is not State.READY:
                logger.info("ptt pressed while state=%s; ignoring (one active utterance at a time)", self.state.name)
                return
            self._begin_recording(new_session=True)

    def on_ptt_up(self) -> None:
        with self._lock:
            if self.state is not State.RECORDING or self._capture is None:
                return
            self._finish_recording()

    def on_cancel(self) -> None:
        with self._lock:
            if self.state not in (State.RECORDING, State.TRANSCRIBING):
                return
            if self._capture is not None:
                self._capture.stop()
                self._capture = None
                self._recording_started_at = None
                if self._current_job_id is not None:
                    self._foreground_target_by_job.pop(self._current_job_id, None)
            cancelled = self._session_job_ids
            self._cancelled_job_ids |= cancelled
            logger.info("session cancelled (%d chunk job(s)): %s", len(cancelled), sorted(cancelled))
            self._session_job_ids = set()
            self._current_job_id = None
            self.state = State.READY

    def on_quit(self) -> None:
        self._shutdown_event.set()

    @property
    def quit_requested(self) -> bool:
        return self._shutdown_event.is_set()

    # -- recording-cap watchdog -------------------------------------------

    def _cap_watchdog_loop(self) -> None:
        while not self._shutdown_event.is_set():
            time.sleep(0.2)
            try:
                self._cap_watchdog_tick()
            except Exception:
                logger.exception("cap watchdog tick failed; continuing")

    def _cap_watchdog_tick(self) -> None:
        with self._lock:
            if self.state is not State.RECORDING or self._recording_started_at is None:
                return
            elapsed = time.monotonic() - self._recording_started_at
            if elapsed < self.settings.recording_limit_seconds:
                return
            still_held = self._ptt_held_probe() if self._ptt_held_probe else False
            if still_held and self._chunk_count_in_session >= MAX_AUTO_RESTART_CHUNKS:
                logger.warning(
                    "hit %d auto-restarted chunks; stopping this session rather than continuing indefinitely "
                    "(release and press the hotkey again to keep dictating)",
                    MAX_AUTO_RESTART_CHUNKS,
                )
                still_held = False
            logger.warning("recording hit the %ds cap; hotkey still held=%s", self.settings.recording_limit_seconds, still_held)
            self._finish_recording()
            if still_held:
                self._begin_recording(new_session=False)

    # -- ASR result handling ---------------------------------------------

    def _result_loop(self) -> None:
        while not self._shutdown_event.is_set():
            try:
                message = self._result_queue.get(timeout=0.25)
            except Exception:
                continue
            try:
                self._handle_result_message(message)
            except Exception:
                logger.exception("failed to handle a result message; continuing")

    def _handle_result_message(self, message: object) -> None:
        with self._lock:
            if isinstance(message, tuple) and message[0] == asr_worker.READY:
                self.state = State.READY
                logger.info("ASR model loaded; ready")
                return
            if isinstance(message, tuple) and message[0] == asr_worker.MODEL_LOAD_FAILED:
                self.state = State.UNAVAILABLE
                self.unavailable_reason = str(message[1])
                logger.error("ASR unavailable: %s", self.unavailable_reason)
                return

            result: asr_worker.TranscribeResult = message  # type: ignore[assignment]

            if result.job_id in self._cancelled_job_ids:
                self._cancelled_job_ids.discard(result.job_id)
                self._foreground_target_by_job.pop(result.job_id, None)
                logger.info("job %d result discarded (cancelled)", result.job_id)
                return

            # Whether this result's job currently owns the foreground state.
            # A chunk from an earlier auto-restart may finish after a newer
            # chunk has already taken over RECORDING/TRANSCRIBING; it is
            # still delivered, it just must not clobber the newer chunk's
            # state (see module docstring).
            is_foreground_job = result.job_id == self._current_job_id
            self._session_job_ids.discard(result.job_id)
            release_time = self._release_time_by_job.pop(result.job_id, None)
            foreground_target = self._foreground_target_by_job.pop(result.job_id, None)

            def _return_to_ready() -> None:
                if is_foreground_job:
                    self.state = State.READY
                    self._current_job_id = None

            if result.error:
                logger.error("job %d ASR failed: %s", result.job_id, result.error)
                _return_to_ready()
                return
            if not result.text:
                logger.info("job %d produced empty transcript, no clipboard change", result.job_id)
                _return_to_ready()
                return

            output_text = result.text
            cleanup_duration_s = None
            if self.settings.mode == "grammar":
                t0 = time.monotonic()
                facts = memory.load_facts() if self.settings.persistent_context else []
                context = " ".join(facts + list(self._recent_context))
                if self.settings.cleanup_backend == "cloud":
                    corrected = cloud_cleanup.correct_grammar_cloud(result.text, context=context, model=self.settings.cloud_model)
                else:
                    corrected = cleanup.correct_grammar(result.text, context=context)
                cleanup_duration_s = time.monotonic() - t0
                if corrected is not None:
                    output_text = corrected
                else:
                    logger.info("job %d cleanup fell back to raw transcript", result.job_id)

            try:
                clipboard.set_clipboard_text(output_text)
                self._recent_context.append(output_text)
                if self.settings.persistent_context:
                    memory.update_memory_async(output_text)
                total_latency = time.monotonic() - release_time if release_time else None
                logger.info(
                    "job %d delivered to clipboard: asr=%.2fs cleanup=%s total_release_to_clipboard=%s",
                    result.job_id,
                    result.duration_s,
                    f"{cleanup_duration_s:.2f}s" if cleanup_duration_s is not None else "n/a",
                    f"{total_latency:.2f}s" if total_latency is not None else "n/a",
                )
                if self.settings.auto_paste:
                    paste.try_auto_paste(foreground_target)
            except clipboard.ClipboardWriteError as exc:
                logger.error("job %d clipboard write failed: %s", result.job_id, exc)
            finally:
                _return_to_ready()
