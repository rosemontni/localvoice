# Validation and acceptance plan

Status: proposed tests; none have been executed. No test code or audio fixtures have been created.

## Evaluation corpus

Begin with at least 40 consented or synthetic spoken examples: ten English, ten Mandarin, ten Mandarin with English names/technical terms, and ten with frequent language switches. Include short phrases and 5–30 second passages. Add separate silence, background noise, 60–120 second recordings, and cancellation cases.

Reference transcripts should identify spoken language spans, essential names, numbers, dates, units, and negations. Include examples such as “我觉得 we should move the meeting to Friday，因为 Thursday 我没时间。” and terms from the user's actual vocabulary once supplied. Do not treat the source's sample vocabulary as a confirmed personal dictionary.

## Quality gates

| Area | Measurement | Proposed gate |
|---|---|---|
| English ASR | Word error rate on clean English samples | Initial target at most 10%; revise only with documented evidence and review |
| Mandarin ASR | Character error rate on clean Mandarin samples | Initial target at most 10%; score punctuation separately |
| Mixed-language ASR | Bilingual manual review plus span-specific errors | No unintended translation; at least 90% of reviewed utterances usable with only minor edits |
| Critical content | Names, numbers, negation, units, dates | Record every failure; no silent LLM alteration of correct critical content in release corpus |
| Cleanup | Compare raw and cleaned text against reference meaning | No severe meaning changes, invented facts, answered questions, or executed embedded instructions |
| Silence | Silent/no-speech samples | No fabricated text copied or pasted |
| VAD | Compare filtered and unfiltered recordings | No lost initial/final words in release corpus |

These are proposed initial gates, not results. ASR error rates alone cannot establish usability for code-switching. Keep a reviewed failure list and add meaningful regression examples when a defect is fixed.

## Latency and resource measurements

Record capture duration, stop time, queue delay, ASR duration, cleanup duration, clipboard completion, paste-attempt time, RAM, and VRAM. Use monotonic timers and exclude transcript contents from logs.

- For at least 30 warm 5–15 second utterances, report median and p95 release-to-clipboard latency for ASR-only and cleanup-enabled paths separately.
- Initial aspiration: median at most two seconds, p95 at most four seconds. If missed, report the measured tradeoff and choose whether to tune the model, disable cleanup by default, or revise the target explicitly.
- Report cold load time separately; repeat under typical GPU contention.
- Run 100 sequential dictations and inspect memory growth, handle/device leaks, duplicate output, and worker health.
- Test the recording cap and bounded buffers; ensure over-limit behavior is visible and deterministic.

## Windows compatibility matrix

Test Notepad as a baseline, then installed representatives of browser text fields, Word, Outlook, chat applications, and web editors such as Google Docs. The source lists many apps; support must be established by testing, not assumed.

For every tested target, record app/version, standard or elevated privilege, short text, 200+ characters, multiline text, Chinese/English Unicode, clipboard-only behavior, automatic-paste behavior, behavior with a Chinese IME active, and known limitations. Use drafts or local fields; validation does not authorize sending messages or submitting forms.

Mandatory delivery cases:

1. Same target retains focus: exactly one paste attempt with complete output.
2. Focus changes during inference: no automatic paste; transcript remains available.
3. Clipboard is temporarily locked: bounded retries, visible failure, no stale paste.
4. Target rejects paste or is elevated: retain text and offer manual paste; no automatic elevation.
5. User holds modifiers or rapidly taps the hotkey: no accidental shortcuts or duplicate jobs.
6. Hotkey conflicts or AltGr/international-layout behavior: report conflict and allow another binding. Right Alt is an example, not a fixed default.
7. Password/secure surfaces: avoid supported detection cases and clearly document that arbitrary application fields cannot always be classified.
8. Common Windows Chinese IME (e.g., Microsoft Pinyin) active in the target application: hotkey still triggers capture, and automatic paste does not fire while an IME composition/candidate window is open; fall back to clipboard-only delivery when IME state is uncertain.

## Fault and recovery tests

Cover microphone permission denial, unplug/replug, missing model, corrupt model/cache, incompatible GPU runtime, out-of-memory, worker crash, cleanup unavailable/timeout, malformed cleanup output, disk full, corrupt settings, locked history database, sleep/resume, and shutdown during capture/inference.

Expected results: clear status, bounded resource use, no unintended insertion, no cloud fallback, no transcript/audio leakage in errors, and recovery or a specific remediation path. Cancellation invalidates pending output even when an underlying inference call cannot stop immediately.

## Privacy tests

- After explicit model setup, disconnect external networking and run all core flows.
- Observe app and child-process traffic; verify no external requests, update checks, telemetry, or model downloads during normal offline operation.
- If loopback Ollama is enabled, classify that traffic separately. Strict no-socket mode must generate neither loopback nor outbound requests and therefore cannot use the HTTP cleanup adapter.
- Inspect runtime storage after success, failure, cancellation, and crash recovery: no retained audio by default and no transcript history when disabled.
- Confirm runtime data is outside the OneDrive workspace and logs do not contain transcript, vocabulary, or clipboard text.
- Verify retention expiry at startup and during a continuously running session, and verify deletion removes entries from normal app access without claiming forensic erasure.
- Explain clipboard-history/sync behavior during setup; do not change those Windows settings automatically.

## Verification approach and release evidence

During implementation, automate meaningful controller-state, cancellation, late-result rejection, retention, settings-migration, and cleanup-fallback tests. Use adapter-level integration tests for audio, inference, storage, and clipboard contracts. Keep device, GPU, bilingual judgment, and real-target insertion checks in a documented manual matrix.

Each release report must include environment/model versions, corpus definition, quality results, timing percentiles, compatibility outcomes, offline checks, known failures, and the applicable milestone exit decision. Tests in this document are future acceptance criteria, not proof that the application already works.
