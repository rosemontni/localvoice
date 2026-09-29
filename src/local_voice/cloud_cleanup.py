"""Optional cloud-based grammar/context correction via the Anthropic API.

Same task and prompt as the local cleanup.py (Ollama/qwen3.5:4b), swapped to
a frontier model for the cases where the local model's limited capability
was the actual bottleneck (see docs/DECISIONS_AND_RISKS.md, 2026-09-28) --
a frontier model can plausibly get context-based corrections right without
the slow, explicit step-by-step reasoning the local model needed.

This is the one feature in this app that sends dictated TEXT (never audio)
to a third party. Off by default (settings.cleanup_backend == "local"); see
docs/REQUIREMENTS.md P01/P06 for the privacy trade-off this represents.

Requires the user's own ANTHROPIC_API_KEY in the environment (read by the
SDK itself) -- never stored in settings.json, never entered or handled by
this app. The model id is pinned to a specific dated snapshot by default
and only read from settings, so upgrading to a newer model is a deliberate
one-line config change, never a silent auto-upgrade.

Never logs transcript contents, per docs/REQUIREMENTS.md P05.
"""

from __future__ import annotations

import logging

from .cleanup import _CONTEXT_BLOCK_TEMPLATE, _PROMPT_TEMPLATE, _is_output_trustworthy

logger = logging.getLogger("local_voice.cloud_cleanup")

DEFAULT_MODEL = "claude-haiku-4-5-20251001"  # pinned dated snapshot; see settings.cloud_model to change it
TIMEOUT_S = 10.0
MAX_TOKENS = 1024

_client = None  # lazily constructed: importing this module must not require the anthropic package or an API key for users who never enable cloud mode


def _get_client():
    global _client
    if _client is None:
        import anthropic  # local import: not a hard dependency of the app, only of this optional feature

        _client = anthropic.Anthropic(timeout=TIMEOUT_S)  # reads ANTHROPIC_API_KEY from the environment
    return _client


def correct_grammar_cloud(text: str, context: str = "", model: str = DEFAULT_MODEL) -> str | None:
    """Same contract as cleanup.correct_grammar: returns a corrected string,
    or None on any failure (missing/invalid API key, network error, rate
    limit, untrustworthy output) -- callers fall back to the raw transcript,
    per F07.
    """
    context_block = _CONTEXT_BLOCK_TEMPLATE.format(context=context) if context.strip() else ""
    prompt = _PROMPT_TEMPLATE.format(text=text, context_block=context_block)

    try:
        client = _get_client()
        # This SDK generation (anthropic>=1.x) dropped raw `temperature`
        # sampling control from the public API entirely. `output_config`'s
        # `effort` looked like the closest replacement lever, but
        # claude-haiku-4-5-20251001 rejects it outright ("This model does
        # not support the effort parameter") -- confirmed live, not assumed.
        # No generation-control knob is passed; the model's default applies.
        response = client.messages.create(
            model=model,
            max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
        corrected = "".join(block.text for block in response.content if block.type == "text").strip()
    except Exception as exc:  # missing/invalid API key, network error, rate limit, SDK error
        logger.warning("cloud cleanup call failed: %s", exc)
        return None

    if corrected.lower().startswith("output:"):  # some models echo the prompt's "Output:" label
        corrected = corrected[len("output:") :].strip()
    if not _is_output_trustworthy(text, corrected):
        logger.warning("cloud cleanup output rejected (empty/wrapper/length-mismatch), falling back to raw text")
        return None
    return corrected
