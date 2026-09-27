"""Minimal CLI for the vocabulary hints list, ahead of the full M4 settings UI.

Usage (with the local-voice env active):
    python scripts/manage_vocabulary.py list
    python scripts/manage_vocabulary.py add "term1" "term2"
    python scripts/manage_vocabulary.py remove "term1"

Terms are passed to faster-whisper as `hotwords` to bias recognition toward
proper nouns/technical terms the ASR model would otherwise miss (e.g. names).
This is a hint, not a guarantee, per docs/REQUIREMENTS.md F09.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from local_voice.config import load_settings, save_settings


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in ("list", "add", "remove"):
        print(__doc__)
        raise SystemExit(1)

    command = sys.argv[1]
    settings = load_settings()

    if command == "list":
        if not settings.vocabulary:
            print("(vocabulary is empty)")
        for term in settings.vocabulary:
            print(term)
        return

    terms = sys.argv[2:]
    if not terms:
        print("no terms given")
        raise SystemExit(1)

    if command == "add":
        for term in terms:
            if term not in settings.vocabulary:
                settings.vocabulary.append(term)
    elif command == "remove":
        settings.vocabulary = [t for t in settings.vocabulary if t not in terms]

    save_settings(settings)
    print(f"vocabulary now has {len(settings.vocabulary)} term(s)")


if __name__ == "__main__":
    main()
