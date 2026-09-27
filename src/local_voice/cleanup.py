"""Optional local grammar-only correction via loopback Ollama.

This is a narrower, safer feature than the full "Clean mode" (filler removal
+ rephrasing) scoped for M3 in docs/ARCHITECTURE.md. Testing this session
found that filler-removal framing invites these small local models to drop
or mistranslate content on complex bilingual sentences (e.g. redundant
Chinese/English restatement), whereas a strict grammar-only instruction
(fix subject-verb agreement/tense only, touch nothing else) held up much
better. See docs/DECISIONS_AND_RISKS.md.

Never logs transcript contents, per docs/REQUIREMENTS.md P05.
"""

from __future__ import annotations

import json
import logging
import urllib.request

logger = logging.getLogger("local_voice.cleanup")

OLLAMA_URL = "http://localhost:11434/api/generate"  # loopback only, per the offline policy decision
MODEL = "qwen3.5:4b"
TIMEOUT_S = 5.0

# One concrete example is what made the model reliably preserve code-switching
# in testing; instructions alone were not enough (see DECISIONS_AND_RISKS.md).
_PROMPT_TEMPLATE = """Fix ONLY these kinds of errors:
1. Grammar mistakes (subject-verb agreement, verb tense, articles).
2. A name or term that is clearly a mistranscription of the SAME name or term that also appears in the reference context below (e.g. different characters with a similar sound to a name spelled correctly in the context) -- correct it to match the context's spelling.
Do not remove any words, including fillers or repeated phrases. Do not rephrase. Do not guess corrections for anything that does not match something in the context. Never translate any word: every Chinese character and every English word in the input must appear in the output in the same language, unchanged, unless it is itself one of the two error types above. Output only the corrected text, nothing else.

Example:
Input: 我觉得 he don't like it 因为 it was too expensive
Output: 我觉得 he doesn't like it 因为 it was too expensive
{context_block}
Now fix this one the same way:
Input: {text}
Output:
"""

_CONTEXT_BLOCK_TEMPLATE = """
Reference context -- earlier text from this same dictation session, which may share names, topics, or recurring terms with the text below. Do not repeat, continue, or copy from it; use it only per rule 2 above:
{context}
"""

_SUSPICIOUS_MARKERS = ("```", "<think", "Input:", "Output:", "Here is", "Here's")


class CleanupUnavailableError(RuntimeError):
    pass


def _is_output_trustworthy(original: str, corrected: str) -> bool:
    if not corrected.strip():
        return False
    if any(marker in corrected for marker in _SUSPICIOUS_MARKERS):
        return False
    ratio = len(corrected) / max(len(original), 1)
    if not (0.7 <= ratio <= 1.3):  # catches dropped/added content; a grammar-only fix shouldn't change length much
        return False
    return True


def correct_grammar(text: str, context: str = "") -> str | None:
    """Return a grammar-corrected version of `text`, or None if the cleanup
    call failed, timed out, or produced output that looks untrustworthy —
    callers should fall back to the raw transcript on None, per F07.

    `context` is recent prior output from the same session (e.g. the last
    few delivered dictations), passed through for disambiguation only --
    never logged, never persisted, and not part of what gets validated or
    returned. See docs/DECISIONS_AND_RISKS.md ("session context").
    """
    context_block = _CONTEXT_BLOCK_TEMPLATE.format(context=context) if context.strip() else ""
    prompt = _PROMPT_TEMPLATE.format(text=text, context_block=context_block)
    payload = json.dumps(
        {
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
            "think": False,
            "options": {"temperature": 0},
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        OLLAMA_URL, data=payload, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
            result = json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # Ollama not running, loopback refused, timeout, malformed response
        logger.warning("cleanup call failed: %s", exc)
        return None

    corrected = result.get("response", "").strip()
    if corrected.lower().startswith("output:"):  # some responses echo the prompt's "Output:" label
        corrected = corrected[len("output:") :].strip()
    if not _is_output_trustworthy(text, corrected):
        logger.warning("cleanup output rejected (empty/wrapper/length-mismatch), falling back to raw text")
        return None
    return corrected
