# Implementation plan

Status: not started. All items below describe future work. Implementation requires a new user instruction to begin.

## Delivery strategy

Validate the language quality and Windows integration before investing in desktop polish. Follow the source's V0.1–V1.0 progression, with compatibility and privacy checks moved early. Each milestone has an exit gate; do not expand scope when a foundational gate fails.

**Near-term target: M0–M1 (V0.1, hotkey-to-clipboard).** M2–M5 remain the documented long-term plan, but the first authorized build should stop at the M1 exit gate and be explicitly reviewed — bilingual ASR quality, latency baseline, and GPU compatibility confirmed on real hardware — before any further milestone is authorized. Treat M2 onward as aspirational scope, not a committed schedule.

## M0 — compatibility and design confirmation

Dependencies: authorization to begin implementation. **Authorized 2026-09-26.**

- [x] Confirm Windows version, GPU/VRAM, installed NVIDIA driver, microphone devices, and available disk space. Result: Windows 11 Home build 26200; RTX 4070 SUPER, 12282 MiB VRAM, driver 610.62; i9-14900F, 31.8 GB RAM; ~1.2 TB free on C:; matches source hardware. Five audio-capable devices detected; physical microphone not yet identified (open decision, see DECISIONS_AND_RISKS.md).
- [x] Verify official faster-whisper/CTranslate2 installation requirements, supported Python version, CUDA/cuDNN compatibility. Result: requires Python <=3.12 (no 3.13 wheels); CTranslate2 >=4.5.0 needs CUDA >=12.3/cuDNN 9. Created a pinned `local-voice` conda env (Python 3.12) via Miniconda; installed faster-whisper 1.2.1 / ctranslate2 4.8.2. Empirically confirmed this machine's CUDA-13-capable driver runs the CUDA-12-built wheel: `ctranslate2.get_cuda_device_count()` returns 1, and Whisper `large-v3-turbo` loaded and ran on GPU with CUDA FP16 (~39s cold load). FFmpeg necessity not separately verified (not needed for the smoke test above).
- [ ] Select and pin compatible dependencies; review redistribution licenses for libraries, Qt, models, and packaging artifacts.
- [x] Whisper `large-v3-turbo` verified: downloaded via faster-whisper/Hugging Face, loads on this machine's GPU with CUDA FP16 in ~39s cold. [ ] Qwen/Ollama tag still unresolved: `qwen3:4b` and `qwen3.5:4b` are both pulled locally, but a first measured cleanup test showed neither is usable as configured (see DECISIONS_AND_RISKS.md) — this needs more evaluation before M3, not before M1.
- [x] Resolve the offline/loopback policy and confirm the proposed defaults in the decision log. Result: loopback-only Ollama traffic allowed by default; strict no-socket mode remains available (see DECISIONS_AND_RISKS.md).
- [ ] Define a small bilingual evaluation corpus with reference transcripts; store personal evaluation audio outside OneDrive and retain it only by explicit choice.

Deliverables: compatibility matrix, pinned environment proposal, model inventory, measured evaluation protocol, and finalized blocking decisions.

Exit gate: one documented supported installation path and a clear local-only runtime boundary. No performance claims based solely on model marketing or the earlier conversation.

Remaining before M0 exit: microphone identification, Qwen version choice, dependency pinning, model download/cache plan, and the evaluation corpus. No environment has been created and no packages or models have been installed yet — see open questions.

## M1 / V0.1 — hotkey to local transcript to clipboard

Dependencies: M0. **Started 2026-09-26.**

- [x] Establish configuration, sanitized logging, controller states, and the inference-worker boundary. Implemented: [config.py](../src/local_voice/config.py), [logging_setup.py](../src/local_voice/logging_setup.py), [controller.py](../src/local_voice/controller.py) (state machine: Starting/Loading/Ready/Recording/Transcribing/Unavailable), [asr_worker.py](../src/local_voice/asr_worker.py) (separate `multiprocessing.Process`, one job at a time, late/cancelled results discarded by job_id).
- [x] Prove file/in-memory audio transcription on the target GPU before integrating global input. Done via an automated smoke test (config round-trip, silence rejection, and a synthesized English WAV transcribed correctly through the real ASR worker process on GPU). This surfaced and fixed a real gap: model *loading* succeeded but actual *transcription* failed with a missing `cublas64_12.dll` until the `nvidia-cublas-cu12`/`nvidia-cudnn-cu12` pip packages were installed (see DECISIONS_AND_RISKS.md).
- [x] Implement bounded microphone capture, push-to-talk press/release, debounce, cancellation, and clean shutdown. [audio_capture.py](../src/local_voice/audio_capture.py) (120s cap, RMS-based silence rejection, sample-rate fallback/resample), [hotkey.py](../src/local_voice/hotkey.py) (pynput; debounces held keys; Esc cancels, F12 quits in this console build).
- [x] Load large-v3-turbo once with CUDA FP16; explicitly use transcription rather than translation. `task="transcribe"` is hardcoded in asr_worker.py, never `"translate"`.
- [x] Implement Unicode clipboard output and simple readiness/recording/error feedback; leave automatic paste disabled. [clipboard.py](../src/local_voice/clipboard.py) (bounded retries, refuses empty text); [main.py](../src/local_voice/main.py) prints state changes to the console (no tray until M4).
- [ ] Handle microphone denial/disconnection, missing local models, model load failure, silence, and GPU memory exhaustion with actionable errors. Model-load failure and microphone-open failure are handled; silence is rejected; disconnection mid-recording and GPU OOM mid-job are caught generically but not yet exercised by a real test. CPU fallback is not implemented (GPU-only for now; explicit CPU fallback remains a later addition, not silent).

This is a console build (no tray/settings UI — that is M4). Run it with `conda activate local-voice` then `python scripts/run_console.py`; hold the configured key (default F9, still an open decision per DECISIONS_AND_RISKS.md) to talk, release to copy to clipboard, Esc to cancel, F12 to quit.

Exit gate: English, Mandarin, and mixed utterances survive the full hotkey-to-clipboard flow; cancellation and silence produce no clipboard change; ASR quality and timing baseline are recorded. **Automated so far:** English via synthesized speech, silence rejection, config persistence. **Still needs a live human test:** Mandarin and mixed-language utterances, and the actual hotkey/microphone/clipboard flow end-to-end — no Chinese TTS voice is installed on this machine and no synthesizeable substitute exists for live mixed-language dictation, so this genuinely needs the user's own voice.

## M2 / V0.2 — controlled automatic insertion

Dependencies: M1 quality gate.

- Capture the intended foreground window at recording start and revalidate before delivery.
- Implement bounded clipboard retries and one Ctrl+V attempt using Windows input APIs after modifiers are released.
- Preserve clipboard output if focus changes, the target is unsupported, or paste is blocked.
- Exercise long text, Unicode, multiline content, keyboard layouts, hotkey conflicts, and applications with different privilege levels.

Exit gate: the supported-application matrix passes; focus changes cause clipboard-only delivery; no duplicate paste occurs under retries or rapid hotkey input.

## M3 / V0.3 — optional local cleanup

Dependencies: M2 and verified local cleanup runtime.

- Add an Ollama adapter restricted to the selected local endpoint policy, with health checks and finite request timeouts.
- Load the selected Qwen model and measure concurrent VRAM consumption with ASR.
- Implement Literal and Clean modes, constrained cleanup instructions, output validation, and raw-text fallback.
- Keep raw output recoverable in memory when persistence is off; provide a copy-raw action.
- Test negation, numeric values, proper nouns, bilingual passages, and dictated instruction-like text.

Exit gate: the critical workflow works reliably: hotkey → mixed-language ASR → optional cleanup → controlled insertion. No severe meaning changes in the reviewed release corpus; cleanup failures still produce recoverable raw text. Record cleanup latency separately.

## M4 / V0.4 — daily-use controls

Dependencies: M3.

- Add PySide6 tray/settings UI and non-focus-stealing recording/processing indicators.
- Add configurable hotkeys, stable microphone selection, Auto/English/Chinese choices, and tested model selection.
- Add bounded custom-vocabulary hints and regression cases for vocabulary changes.
- Introduce conservative Silero VAD filtering; compare against M1 recordings to detect clipped initial/final speech.
- Add opt-in SQLite history with copy, text cleanup reprocessing, deletion, and scheduled retention.
- Surface local model availability and explicit setup actions without background downloads.

Exit gate: settings survive restart, history-off produces no transcript persistence, enabled retention works across restarts and long-running sessions, and VAD does not regress code-switching or speech boundaries.

## M5 / V1.0 — packaging and reliability

Dependencies: M4 and full validation matrix.

- Select packaging based on verified native dependency and license constraints; test on a clean Windows account or machine.
- Separate application installation from large model acquisition; expose download sizes and storage locations during explicit setup.
- Add optional start with Windows and predictable model-warming status.
- Verify crash recovery, sleep/resume, microphone replacement, stale worker cleanup, and sanitized diagnostic export.
- Document installation, offline setup, supported targets, manual-paste fallback, troubleshooting, retention, and uninstall behavior.
- Perform latency tuning only after quality and reliability pass; compare warm/cold measurements and GPU contention.

Exit gate: reproducible installation, documented dependency/model versions, passing acceptance matrix, no external runtime traffic in offline mode, and stable repeated-session operation.

Automatic updates remain a separate later decision: they conflict with strict offline expectations unless explicitly enabled and must include a verified update/distribution design.

## Later backlog

Hands-free activation; Professional/Notes/Email modes; explicit voice commands; selection rewriting; opt-in cursor context; language-aware automatic cleanup routing; and a possible native .NET shell. Each needs separate UX, privacy, and regression criteria.

## Scheduling and change control

Do not commit calendar estimates before M0 establishes dependency compatibility and M1 measures quality. Track progress by the exit gates above. If mixed-language quality fails, evaluate decoding settings and model alternatives before polishing the UI. Any proposed change to cloud use, audio retention, ambient listening, or automatic context capture requires revisiting the requirements.
