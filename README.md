# Local Voice

A local Windows dictation application for Mandarin, English, and mixed Chinese-English speech: hold a hotkey, speak, release, and get the transcript on your clipboard (and optionally auto-pasted) — fully local GPU transcription, no cloud.

**Status: M0/M1/M2 implemented and in daily use; M4 (tray UI) not started.** See [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) for milestone status and [docs/DECISIONS_AND_RISKS.md](docs/DECISIONS_AND_RISKS.md) for the significant findings/fixes made building this (several real bugs found and fixed: a `SendInput` struct-size bug that silently broke auto-paste, Whisper decoding Chinese as pinyin instead of Han characters, a duplicate-instance clipboard race).

## What works today

- Global push-to-talk hotkey (default F9), auto-restarts into a new chunk if you hit the recording cap without releasing (no lost audio on a forgotten key)
- Local GPU transcription (faster-whisper, `large-v3`), auto-detects English/Mandarin/mixed and preserves code-switching (never translates)
- Windows clipboard delivery, with optional one-shot auto-paste (`SendInput`, focus-rechecked, never retried)
- Optional local grammar-cleanup pass (small local LLM via Ollama), with session context and a small persisted cross-session memory of names/recurring terms (see `scripts/manage_memory.py`) to help disambiguate homophone errors
- Vocabulary hints for names/terms the model otherwise misses (see `scripts/manage_vocabulary.py`)

## Running it

```bash
conda activate local-voice
python scripts/run_console.py
```

Console-only for now (no tray/settings UI yet — see M4 in the implementation plan). Hold the configured hotkey and speak, release to transcribe. Esc cancels, F12 quits.

```bash
python -m pytest tests/       # unit tests
python scripts/smoke_test_gpu.py   # GPU/model smoke test (loads the model, needs a few minutes first run)
```

## Documents

1. [Requirements](docs/REQUIREMENTS.md) — scope, user workflow, privacy requirements, and release boundaries.
2. [Architecture](docs/ARCHITECTURE.md) — components, state flow, data handling, and Windows integration.
3. [Implementation plan](docs/IMPLEMENTATION_PLAN.md) — milestones, what's done, what's next.
4. [Validation plan](docs/VALIDATION_PLAN.md) — bilingual quality, latency, reliability, and privacy acceptance tests.
5. [Decisions and risks](docs/DECISIONS_AND_RISKS.md) — defaults, resolved/open questions, and the real bugs found along the way.
6. [Source notes](docs/SOURCE_NOTES.md) — provenance of the original project brief.

## Layout

- `src/local_voice/` — the application (controller/state machine, audio capture, ASR worker process, hotkey, clipboard, auto-paste, cleanup, cross-session memory).
- `scripts/` — entry point (`run_console.py`), a GPU smoke test, and small CLIs for vocabulary hints and memory inspection.
- `tests/` — unit tests (fast, no GPU/mic required — they fake out hardware-dependent pieces).

## Runtime data

Settings, logs, and the vocabulary/memory files live under `%LOCALAPPDATA%\LocalVoice`, independent of wherever this repository itself is checked out — deliberately, since this repo may be cloud-synced (OneDrive, etc.) and runtime data (logs, cached models, the small cross-session memory file) should not be.

## Next step

M4: a real tray/settings UI to replace the console build, per [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md).
