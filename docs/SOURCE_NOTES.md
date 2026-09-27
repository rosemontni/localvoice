# Source notes

Prepared: 2026-09-26.

Primary source: [Local Chinese English Dictation Solution — shared ChatGPT conversation](https://chatgpt.com/share/6ab83d3d-975c-83e9-aa79-06b257f6f0ae).

The shared page was read in the browser. Its visible content includes an initial recommendation, a ten-phase custom application plan, version milestones, and a clarification that no project folder had yet been created. This document summarizes the source; it is not a transcript.

## Direction from the conversation

- Build a local alternative to Typeless on Windows for English, Mandarin, and intentional code-switching.
- Target hardware described in the source: Intel i9-14900F, 32 GB RAM, NVIDIA RTX 4070 Super. These specifications have not been independently inspected on this computer.
- Start with Python, faster-whisper, Whisper large-v3-turbo, CUDA FP16, and global push-to-talk.
- Deliver text through the clipboard, then add automatic paste.
- Add optional Qwen3 4B cleanup through Ollama, preserving language and meaning.
- Add Silero VAD, vocabulary, PySide6 tray/settings UI, and SQLite history.
- Progress from V0.1 clipboard dictation to V0.3 cleanup and insertion, then desktop polish and packaging.
- Consider C#/.NET only after a stable Python implementation; it is not part of the initial build.

## Interpretation and additions

The source is a design proposal, not a verified implementation specification. Its performance, compatibility, memory-use, and third-party application claims have not been treated as established facts. Exact package versions, CUDA dependencies, model identifiers, licenses, and deployment requirements must be checked against official documentation during the first implementation milestone.

The accompanying documents add explicit failure handling, focus-change protection, cancellation semantics, measurable validation gates, privacy defaults, and an implementation sequence. These are proposed engineering decisions, not additional user instructions from the source.

The source describes offline mode as making zero network requests while also proposing Ollama. A local Ollama HTTP connection is a network request over loopback. The plan distinguishes no external network traffic from a stricter no-socket mode and records this as an open decision.

The original user instruction authorized only planning documents. A later instruction ("prepare to implement it", 2026-09-26) authorized starting M0; see IMPLEMENTATION_PLAN.md and DECISIONS_AND_RISKS.md for what has been done since.
