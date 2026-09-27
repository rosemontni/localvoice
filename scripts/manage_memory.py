"""Inspect or clear the persisted cross-session memory (standing facts).

Usage (with the local-voice env active):
    python scripts/manage_memory.py list
    python scripts/manage_memory.py clear
    python scripts/manage_memory.py remove "<exact fact text>"

This is a small, bounded, abstracted list -- names and recurring
terms/topics, never raw transcripts -- used to help the grammar-cleanup
step disambiguate recurring names across restarts. See
docs/DECISIONS_AND_RISKS.md and local_voice/memory.py.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from local_voice import memory


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in ("list", "clear", "remove"):
        print(__doc__)
        raise SystemExit(1)

    command = sys.argv[1]

    if command == "list":
        facts = memory.load_facts()
        if not facts:
            print("(no standing facts remembered yet)")
        for fact in facts:
            print(fact)
        return

    if command == "clear":
        memory.save_facts([])
        print("cleared all standing facts")
        return

    if command == "remove":
        if len(sys.argv) < 3:
            print("usage: python scripts/manage_memory.py remove \"<exact fact text>\"")
            raise SystemExit(1)
        target = sys.argv[2]
        facts = memory.load_facts()
        remaining = [f for f in facts if f != target]
        memory.save_facts(remaining)
        print(f"removed {len(facts) - len(remaining)} matching fact(s); {len(remaining)} remain")


if __name__ == "__main__":
    main()
