"""Bounded, abstracted cross-session context ("standing facts").

Deliberately NOT a raw transcript log: after each delivered dictation, a
small local LLM call extracts at most one short fact worth remembering
across future sessions (a name, a recurring project/topic, a technical
term) -- ordinary conversational content extracts nothing. Facts are capped
in count and length, deduplicated against existing ones, and persisted to a
single small JSON file. This exists specifically to help the cleanup step
recognize recurring names/terms across restarts, extending the in-session
context in controller.py to survive them. See docs/DECISIONS_AND_RISKS.md.

Runs as fire-and-forget background work after clipboard delivery: it must
never add latency to the dictation-to-clipboard path.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import urllib.request

from .cleanup import MODEL, OLLAMA_URL, TIMEOUT_S
from .config import RUNTIME_ROOT

logger = logging.getLogger("local_voice.memory")

MEMORY_PATH = RUNTIME_ROOT / "memory.json"
MAX_FACTS = 30
MAX_FACT_CHARS = 80

_EXTRACT_PROMPT_TEMPLATE = """From the dictated text below, extract at most one short standing fact worth remembering for FUTURE, unrelated dictations -- a proper name, a recurring project/topic, or a specific technical term written as a brief note under 12 words. Only extract something that looks likely to recur later (a name, a named project, a specific term). Ordinary conversational content, one-off statements, and anything without a proper noun or specific recurring term are NOT worth extracting. If there is nothing worth remembering, respond with exactly: NONE

Examples:
Text: 我们在讨论马友友的大提琴演出
Fact: 马友友 -- 大提琴家 (cellist)

Text: he doesn't have enough time because we were too busy last week
Fact: NONE

Now extract from this text:
Text: {text}
Fact:
"""


def _shingles(s: str, n: int = 2) -> set[str]:
    # Character-level, not word-level: Chinese has no spaces between words,
    # so a whitespace-split "shared words" check barely detects any overlap
    # between e.g. "大提琴家 (cellist)" and "著名大提琴家" even though the
    # latter literally contains the former as a substring.
    s = s.lower()
    return {s[i : i + n] for i in range(len(s) - n + 1)} if len(s) >= n else {s}


def _too_similar(a: str, b: str) -> bool:
    sa, sb = _shingles(a), _shingles(b)
    if not sa or not sb:
        return False
    overlap = len(sa & sb) / min(len(sa), len(sb))
    return overlap >= 0.5  # shares most of its shorter fact's substrings with an existing one


def load_facts() -> list[str]:
    try:
        data = json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
        facts = data.get("facts", [])
        return [f for f in facts if isinstance(f, str)][:MAX_FACTS]
    except (OSError, json.JSONDecodeError, AttributeError):
        return []


def save_facts(facts: list[str]) -> None:
    RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
    tmp_path = MEMORY_PATH.with_suffix(".tmp")
    tmp_path.write_text(json.dumps({"facts": facts}, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp_path, MEMORY_PATH)


def _extract_fact(text: str) -> str | None:
    prompt = _EXTRACT_PROMPT_TEMPLATE.format(text=text)
    payload = json.dumps(
        {"model": MODEL, "prompt": prompt, "stream": False, "think": False, "options": {"temperature": 0}}
    ).encode("utf-8")
    request = urllib.request.Request(OLLAMA_URL, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
            result = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        logger.warning("memory extraction call failed: %s", exc)
        return None

    fact = result.get("response", "").strip()
    if fact.lower().startswith("fact:"):
        fact = fact[len("fact:") :].strip()
    if not fact or fact.upper() == "NONE" or len(fact) > MAX_FACT_CHARS:
        return None
    return fact


def _update_memory(text: str) -> None:
    try:
        fact = _extract_fact(text)
        if not fact:
            return
        facts = load_facts()
        if any(_too_similar(fact, existing) for existing in facts):
            return
        facts.append(fact)
        if len(facts) > MAX_FACTS:
            facts = facts[-MAX_FACTS:]
        save_facts(facts)
        logger.info("memory: added a standing fact (%d/%d total)", len(facts), MAX_FACTS)
    except Exception:
        logger.exception("memory update failed; continuing")


def update_memory_async(text: str) -> None:
    """Fire-and-forget: never blocks the caller, never raises."""
    threading.Thread(target=_update_memory, args=(text,), daemon=True).start()
