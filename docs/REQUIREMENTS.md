# Requirements

Status: proposed specification; planning only.

## Goal and workflow

Provide private, responsive Windows dictation: hold a configurable hotkey, speak English, Mandarin, or mixed speech, release, optionally clean the transcript, and insert the result into the intended application.

The primary target is the Windows 11 desktop described in the source. Confirm OS, microphone, driver, available GPU memory, and hardware before selecting exact runtime versions.

## Functional requirements

| ID | Requirement | First release |
|---|---|---|
| F01 | Capture microphone audio only during explicit push-to-talk; cancel without producing output. | V0.1 |
| F02 | Run local multilingual transcription with translation disabled; retain Chinese and English within the same utterance. | V0.1 |
| F03 | Copy successful nonempty output to the Windows Unicode clipboard and retain it for manual paste. | V0.1 |
| F04 | Expose recording, processing, ready, cancellation, and actionable error states. | V0.1 |
| F05 | Automatically paste once when the original target is still appropriate; retain manual-paste fallback. | V0.2 |
| F06 | Offer optional local cleanup that preserves meaning, language switches, names, numbers, and negation; retain access to raw text. | V0.3 |
| F07 | Fall back to raw transcription if cleanup times out, fails, or returns unusable output. | V0.3 |
| F08 | Provide tray controls, hotkey and microphone settings, and language selection: Auto, English, Chinese. | V0.4 |
| F09 | Allow editable custom vocabulary as recognition hints, without promising exact recognition. | V0.4 |
| F10 | Offer opt-in local transcript history with copy, reprocess, delete, and retention controls. | V0.4 |
| F11 | Add VAD-based silence rejection and bounded trimming without cutting off speech. | V0.4 |
| F12 | Provide explicit model setup/status and selection among tested local models. | V0.4 |
| F13 | Package installation, optional start with Windows, non-focus-stealing status indicator, and recovery behavior. | V1.0 |

Literal mode in V0.3 means raw ASR output, including ASR punctuation, with no LLM rewrite. Clean mode removes obvious filler and adds punctuation conservatively. Professional, Notes, and Email are later features requiring separate meaning-preservation tests.

A narrower **grammar mode** was implemented 2026-09-26, ahead of the M3 schedule, at explicit user request ("Typeless can correct minor grammar mistakes, can you also do that?"). It fixes only subject-verb agreement/tense/article errors via a local LLM call with an output-safety check (falls back to raw text on empty/wrapper/length-mismatch output), and does not attempt filler removal or rephrasing. Testing this session found that broader "clean up and remove fillers" framing caused the same local models to drop redundant content and mistranslate connector words on complex bilingual sentences, while the strict grammar-only framing held up; see docs/DECISIONS_AND_RISKS.md. Full Clean mode (F06/F07 as originally scoped) remains unimplemented pending the M3 bilingual corpus gate.

**P04 amendment, 2026-09-27:** a new, narrower exception to "no history by default" was added at explicit user request: `local_voice/memory.py` persists a small, bounded (30 entries, ~80 chars each) list of *abstracted standing facts* (names, recurring projects/terms) extracted from dictations by a local LLM call -- never raw transcript text -- to help the grammar-cleanup step disambiguate recurring names across restarts (homophone correction was otherwise limited to the current session; see DECISIONS_AND_RISKS.md). On by default (`settings.persistent_context`), unlike full transcript history (F10, still off by default). Inspect or clear it with `scripts/manage_memory.py`.

**P01 amendment, 2026-09-28:** an opt-in cloud grammar-cleanup backend was added at explicit user request, after local-model testing (M0/M3 findings above) hit a real capability ceiling on homophone/context correction that a frontier model can plausibly clear without the local model's need for slow explicit reasoning (see the Typeless-architecture discussion and the model recommendation in DECISIONS_AND_RISKS.md, 2026-09-28). `local_voice/cloud_cleanup.py` sends only the already-transcribed dictated *text* (never audio, never the raw waveform) to the Anthropic API when `settings.cleanup_backend == "cloud"`; the default remains `"local"` (Ollama, fully on-device). The model id is pinned to a specific dated snapshot (`settings.cloud_model`) and never auto-floats to a newer release. Requires the user's own `ANTHROPIC_API_KEY` in the environment; never stored in settings.json or handled by the app itself.

## Privacy and operational requirements

| ID | Requirement |
|---|---|
| P01 | Audio processing always remains on this machine, with no exception. Transcript *text* (never audio) may optionally be sent to a cloud LLM for the grammar-cleanup step only, if the user explicitly enables it (`settings.cleanup_backend = "cloud"`, off by default) -- see the 2026-09-28 amendment below. |
| P02 | Audio remains in memory by default. No saved recordings; any unavoidable temporary file is removed on success, error, cancellation, and next startup after a crash. |
| P03 | Keep runtime data outside the OneDrive workspace, under a configurable local application-data directory. |
| P04 | History is off by default. When enabled, propose seven-day retention, with 24-hour and never-expire options. |
| P05 | No telemetry or transcript/audio contents in routine logs. Diagnostics report stages, timing, versions, and sanitized errors. |
| P06 | Model/dependency downloads occur only during an explicit setup/update action. Normal offline operation must not trigger downloads or external update checks. |
| P07 | Clipboard retention is explicit in settings and onboarding; Windows clipboard history or sync may separately retain or transmit clipboard contents. Do not alter OS clipboard settings automatically. |
| P08 | Local persistence is not a promise of encryption or forensic secure deletion. Document retention and deletion behavior accurately. |

## Experience and performance

- Keep the UI responsive during recording, model loading, transcription, and cleanup.
- Keep models warm when feasible; report cold-start readiness separately from normal dictation latency.
- Proposed warm target: median release-to-clipboard latency at most two seconds for 5–15 second utterances; p95 at most four seconds. Measure ASR-only and cleanup paths separately before committing to a product guarantee.
- Never silently insert into a different foreground application after processing.
- Silence, cancellation, or a failed transcription must not overwrite the clipboard with an empty or stale result.
- Start with one active utterance; reject additional recording requests while processing with clear feedback. Do not queue unexpected future pastes.
- Proposed recording cap: 120 seconds, with an explicit limit indication and deterministic stop behavior.

## Out of scope for the initial releases

Always-on listening, cloud providers, voice-driven execution of commands, selection rewriting, cursor-context capture, automatic translation, mobile/macOS/Linux support, and a C# rewrite. Automatic updates are deferred until offline behavior and a secure distribution/update design are agreed.
