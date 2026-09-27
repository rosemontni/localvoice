# Local Voice

Planning documents for a local Windows dictation application supporting Mandarin, English, and mixed Chinese-English speech.

**Status: M0 (compatibility and design confirmation) in progress.** No application code has been written yet. A dedicated `local-voice` Python 3.12 conda environment exists with faster-whisper/ctranslate2/sounddevice/pywin32 installed, and the Whisper `large-v3-turbo` model plus two candidate Ollama cleanup models (`qwen3:4b`, `qwen3.5:4b`) have been downloaded for evaluation. See [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) for M0 checklist status and [docs/DECISIONS_AND_RISKS.md](docs/DECISIONS_AND_RISKS.md) for what's resolved vs. still open — notably, the cleanup model choice is unresolved after a first measured test.

## Documents

1. [Requirements](docs/REQUIREMENTS.md) — scope, user workflow, privacy requirements, and release boundaries.
2. [Architecture](docs/ARCHITECTURE.md) — proposed components, state flow, data handling, and Windows integration.
3. [Implementation plan](docs/IMPLEMENTATION_PLAN.md) — ordered work packages, dependencies, and completion gates.
4. [Validation plan](docs/VALIDATION_PLAN.md) — bilingual quality, latency, reliability, and privacy acceptance tests.
5. [Decisions and risks](docs/DECISIONS_AND_RISKS.md) — proposed defaults, unresolved questions, and technical risks.
6. [Source notes](docs/SOURCE_NOTES.md) — provenance and interpretation of the shared conversation.

## Project location

`C:\Users\xliup\OneDrive\Documents\codex\local-voice`

This is the documentation and future source-code workspace. Because it is under OneDrive, future recordings, transcript history, logs containing personal text, and model caches must live outside this folder. Proposed runtime location: `%LOCALAPPDATA%\LocalVoice`.

## Next step

Review the planning decisions, then explicitly authorize implementation. The first implementation milestone will validate bilingual transcription and GPU compatibility before building the full desktop experience.
