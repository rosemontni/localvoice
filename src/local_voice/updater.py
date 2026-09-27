"""Check GitHub Releases for a newer version.

This hits an external network endpoint automatically (at most once per day),
which is a narrow, explicit exception to "no automatic external network
activity" (REQUIREMENTS.md P06) -- same pattern as memory.py's extraction
calls, added at explicit user request. Gated by
settings.check_for_updates; a manual "Check Now" path (check_now()) always
works regardless of the daily cache. Never raises, never blocks startup
noticeably (network timeout is short) -- an update check must never break
the app if offline.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.request

from ._version import __version__
from .config import RUNTIME_ROOT

logger = logging.getLogger("local_voice.updater")

RELEASES_API = "https://api.github.com/repos/rosemontni/localvoice/releases/latest"
_LAST_CHECK_PATH = RUNTIME_ROOT / "last_update_check.json"
_CHECK_INTERVAL_S = 24 * 60 * 60
_TIMEOUT_S = 5.0


def _parse_version(v: str) -> tuple[int, ...]:
    v = v.strip().lstrip("vV")
    parts = []
    for p in v.split("."):
        digits = "".join(c for c in p if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def check_now() -> dict | None:
    """Returns {"version": tag, "url": release page} if newer than the
    running version is available on GitHub, else None. Never raises."""
    try:
        request = urllib.request.Request(
            RELEASES_API,
            headers={"Accept": "application/vnd.github+json", "User-Agent": "local-voice-updater"},
        )
        with urllib.request.urlopen(request, timeout=_TIMEOUT_S) as response:
            data = json.loads(response.read().decode("utf-8"))
        latest_tag = data.get("tag_name", "")
        if latest_tag and _parse_version(latest_tag) > _parse_version(__version__):
            return {"version": latest_tag, "url": data.get("html_url", "https://github.com/rosemontni/localvoice/releases")}
        return None
    except Exception as exc:  # offline, rate-limited, GitHub down, no releases yet, etc.
        logger.info("update check skipped/failed (not an error if offline): %s", exc)
        return None


def maybe_check_once_per_day() -> dict | None:
    """Same as check_now(), but silently skips if already checked within
    the last day, so this can be called on every startup without spamming
    the GitHub API."""
    try:
        last = json.loads(_LAST_CHECK_PATH.read_text(encoding="utf-8")).get("last_check", 0)
    except (OSError, json.JSONDecodeError):
        last = 0
    if time.time() - last < _CHECK_INTERVAL_S:
        return None

    result = check_now()
    try:
        RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
        _LAST_CHECK_PATH.write_text(json.dumps({"last_check": time.time()}), encoding="utf-8")
    except OSError:
        pass
    return result
