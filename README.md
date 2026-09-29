<p align="center">
  <img src="assets/banner.svg" alt="Local Voice — local, offline dictation for English, Mandarin &amp; mixed speech" width="100%">
</p>

# Local Voice

A local Windows dictation application for Mandarin, English, and mixed Chinese-English speech: hold a hotkey, speak, release, and get the transcript on your clipboard (and optionally auto-pasted) — fully local GPU transcription, no cloud.

**Status: M0/M1/M2 implemented and in daily use; a minimal system tray build, a Windows installer, and update checking have also been added ahead of the M4/M5 schedule.** See [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) for milestone status and [docs/DECISIONS_AND_RISKS.md](docs/DECISIONS_AND_RISKS.md) for the significant findings/fixes made building this (several real bugs found and fixed: a `SendInput` struct-size bug that silently broke auto-paste, Whisper decoding Chinese as pinyin instead of Han characters, a duplicate-instance clipboard race).

Licensed under [Apache 2.0](LICENSE).

## What works today

- Global push-to-talk hotkey (default F9), auto-restarts into a new chunk if you hit the recording cap without releasing (no lost audio on a forgotten key)
- Local GPU transcription (faster-whisper, `large-v3`), auto-detects English/Mandarin/mixed and preserves code-switching (never translates)
- Windows clipboard delivery, with optional one-shot auto-paste (`SendInput`, focus-rechecked, never retried)
- Optional grammar-cleanup pass, with session context and a small persisted cross-session memory of names/recurring terms (see `scripts/manage_memory.py`) to help disambiguate homophone errors — backed by a local LLM via Ollama by default, or optionally a cloud model (Claude Haiku 4.5) for better context-based correction at the cost of sending dictated text (never audio) off-device; see "Cloud cleanup" below
- Vocabulary hints for names/terms the model otherwise misses (see `scripts/manage_vocabulary.py`)

## Installing

Download the latest installer from [Releases](https://github.com/rosemontni/localvoice/releases) and run it. It's a small (~2 MB) installer that then sets up a dedicated Python environment and downloads the required packages (roughly 2 GB, CUDA runtime libraries + faster-whisper/ctranslate2/etc. — the Whisper model itself downloads separately, on first dictation). No admin rights needed; it installs per-user with a Start Menu entry and an optional desktop shortcut, both launching the app in the system tray (no console window). Right-click the tray icon to check for updates, open logs, or quit.

The optional grammar-cleanup/homophone-correction feature needs [Ollama](https://ollama.com) installed separately (with a model such as `qwen3.5:4b` pulled) — the app works without it, just without that feature.

### Cloud cleanup (optional)

The local cleanup model sometimes can't fix a wrong character/homophone even with context, simply because it's a small model. Switching the cleanup backend to a frontier model via the Anthropic API fixes this in testing, at the cost of sending your already-transcribed dictated **text** (never audio) to Anthropic for that step. Off by default.

To enable it:
1. Set `ANTHROPIC_API_KEY` in your environment yourself (e.g. `setx ANTHROPIC_API_KEY "sk-ant-..."` in your own terminal) — the app reads it from the environment and never stores or displays it.
2. In `%LOCALAPPDATA%\LocalVoice\settings.json`, set `"cleanup_backend": "cloud"`.

The model id (`cloud_model` in settings) is pinned to a specific dated snapshot and never auto-upgrades — bumping to a newer model is a deliberate one-line config change, so a model update never silently changes behavior you've come to rely on.

## Running from source (development)

```bash
conda activate local-voice
python scripts/run_console.py   # console build: visible logs, good for debugging
python scripts/run_tray.py      # tray build: same as the installed app
```

Hold the configured hotkey and speak, release to transcribe. Esc cancels, F12 quits (console build) / right-click → Quit (tray build).

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

- `src/local_voice/` — the application (controller/state machine, audio capture, ASR worker process, hotkey, clipboard, auto-paste, cleanup, cross-session memory, tray app, update checker).
- `scripts/` — entry points (`run_console.py`, `run_tray.py`), a GPU smoke test, and small CLIs for vocabulary hints and memory inspection.
- `tests/` — unit tests (fast, no GPU/mic required — they fake out hardware-dependent pieces).
- `installer/` — the Inno Setup script and first-run environment setup used to build the Windows installer (`installer/local_voice.iss`; build with `ISCC installer\local_voice.iss` from the repo root, needs [Inno Setup](https://jrsoftware.org/isinfo.php)).
- `assets/` — the app icon (`icon.ico`) and the script that generates it.

## Runtime data

Settings, logs, and the vocabulary/memory files live under `%LOCALAPPDATA%\LocalVoice`, independent of wherever this repository itself is checked out — deliberately, since this repo may be cloud-synced (OneDrive, etc.) and runtime data (logs, cached models, the small cross-session memory file) should not be.

## Next step

A settings UI (the tray app currently has no way to change settings except editing `settings.json` by hand) and the remaining M4/M5 hardening items, per [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md).
