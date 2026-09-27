"""Windows Unicode clipboard delivery.

Clipboard-only in M1: no automatic paste (that is M2). Bounded retries if
another process owns the clipboard; never write an empty string, per
docs/REQUIREMENTS.md F03 and the "never overwrite with empty/stale result"
experience requirement.
"""

from __future__ import annotations

import logging
import time

import win32clipboard
import win32con

logger = logging.getLogger("local_voice.clipboard")

MAX_RETRIES = 5
RETRY_DELAY_S = 0.05


class ClipboardWriteError(RuntimeError):
    pass


def set_clipboard_text(text: str) -> None:
    if not text:
        raise ValueError("refusing to write empty text to the clipboard")

    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            win32clipboard.OpenClipboard()
            try:
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
            finally:
                win32clipboard.CloseClipboard()
            return
        except Exception as exc:  # another app owns the clipboard, or access denied
            last_error = exc
            logger.warning("clipboard write attempt %d/%d failed: %s", attempt, MAX_RETRIES, exc)
            time.sleep(RETRY_DELAY_S)

    raise ClipboardWriteError(f"clipboard busy after {MAX_RETRIES} attempts: {last_error}")
