"""Dedicated inference worker process: load once, transcribe one job at a time.

Runs in its own process (not thread) per docs/ARCHITECTURE.md, so a hung
runtime can be killed/restarted without freezing the caller, and so results
for a stale job_id can simply be discarded by the controller (late-result
rejection) rather than requiring true mid-inference cancellation.
"""

from __future__ import annotations

import logging
import multiprocessing as mp
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


def _add_nvidia_dll_dirs() -> None:
    """Windows-only: pip-installed nvidia-cublas-cu12/nvidia-cudnn-cu12 wheels
    place their DLLs under a `nvidia.<pkg>` namespace package's own `bin/`
    directory, which is not on the default DLL search path or PATH.
    ctranslate2's native loader on Windows falls back to plain PATH, so
    os.add_dll_directory() alone is not enough (see docs/DECISIONS_AND_RISKS.md,
    "cublas64_12.dll is not found").
    """
    if sys.platform != "win32":
        return
    import importlib.util

    bin_dirs: list[str] = []
    for module_name in ("nvidia.cublas", "nvidia.cudnn", "nvidia.cuda_nvrtc"):
        spec = importlib.util.find_spec(module_name)
        if spec is None or not spec.submodule_search_locations:
            continue
        bin_dir = Path(next(iter(spec.submodule_search_locations))) / "bin"
        if bin_dir.is_dir():
            bin_dirs.append(str(bin_dir))

    for bin_dir in bin_dirs:
        try:
            os.add_dll_directory(bin_dir)
        except (OSError, AttributeError):
            pass
    if bin_dirs:
        os.environ["PATH"] = os.pathsep.join(bin_dirs) + os.pathsep + os.environ.get("PATH", "")


@dataclass
class TranscribeJob:
    job_id: int
    audio: np.ndarray
    language: str  # "auto" | "en" | "zh"
    hotwords: str | None = None  # space-joined vocabulary hints; never logged (may contain personal terms)


@dataclass
class TranscribeResult:
    job_id: int
    text: str | None
    duration_s: float
    error: str | None = None


SHUTDOWN = "__shutdown__"
READY = "__ready__"
MODEL_LOAD_FAILED = "__model_load_failed__"

# Whisper can decode Chinese speech as romanized pinyin instead of Han
# characters (a documented behavior, not a language-detection failure --
# detection was correct in testing this session, the script chosen for
# output was not). Seeding a short Chinese-character initial_prompt biases
# the decoder toward Han-script output. See docs/DECISIONS_AND_RISKS.md.
_ZH_SCRIPT_INITIAL_PROMPT = "这是一段中英文混合的语音输入，包含地名、人名和技术术语。"


def worker_main(job_queue: "mp.Queue[Any]", result_queue: "mp.Queue[Any]", model_size: str, device: str, compute_type: str) -> None:
    logger = logging.getLogger("local_voice.asr_worker")
    logging.basicConfig(level=logging.INFO)

    try:
        _add_nvidia_dll_dirs()
        # huggingface_hub's newer Xet-based chunked download path was found
        # (2026-09-27, live testing) to silently produce a dangling blob
        # reference with none of the actual model weights downloaded --
        # model loading reports success in ~3s (vs. a real ~3GB download
        # taking over a minute) and produces garbled/hallucinated
        # transcriptions, with no error anywhere. Forcing the classic HTTP
        # download path avoids this entirely. See docs/DECISIONS_AND_RISKS.md.
        os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
        from faster_whisper import WhisperModel

        model = WhisperModel(model_size, device=device, compute_type=compute_type)
    except Exception as exc:  # missing model, CUDA/driver failure, OOM at load time, etc.
        logger.error("model load failed: %s", exc)
        result_queue.put((MODEL_LOAD_FAILED, str(exc)))
        return

    result_queue.put((READY, None))

    while True:
        message = job_queue.get()
        if message == SHUTDOWN:
            return
        job: TranscribeJob = message
        t0 = time.monotonic()
        try:
            task_language = None if job.language == "auto" else job.language
            segments, _info = model.transcribe(
                job.audio,
                task="transcribe",  # never "translate": preserve code-switching (docs/ARCHITECTURE.md)
                language=task_language,
                vad_filter=False,  # VAD arrives at M4; M1 relies on the caller's own silence check
                hotwords=job.hotwords,
                initial_prompt=_ZH_SCRIPT_INITIAL_PROMPT,
                # Default True: conditions each segment's decoding on the text already
                # produced for this clip. A well-documented cause of Whisper dropping or
                # hallucinating content on longer audio -- an early misstep (background
                # noise, the hotkey's own keypress sound, hesitation) can cascade into
                # skipped/corrupted later segments. Found 2026-09-27 after a user report
                # of a long dictation where only the ending was transcribed.
                condition_on_previous_text=False,
            )
            text = "".join(segment.text for segment in segments).strip()
            duration_s = time.monotonic() - t0
            result_queue.put(TranscribeResult(job_id=job.job_id, text=text, duration_s=duration_s))
        except Exception as exc:  # GPU OOM mid-job, decode failure, etc.
            duration_s = time.monotonic() - t0
            logger.error("job %s failed: %s", job.job_id, exc)
            result_queue.put(TranscribeResult(job_id=job.job_id, text=None, duration_s=duration_s, error=str(exc)))
