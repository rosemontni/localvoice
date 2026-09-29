"""Windows-native single-instance guard via a named mutex.

Without this, double-launching the app (e.g. clicking the Start Menu
shortcut twice while the first launch is still loading the model, ~3-5s)
creates two competing hotkey listeners and ASR pipelines racing the same
clipboard -- this is a real bug that was hit live, not a hypothetical; see
docs/DECISIONS_AND_RISKS.md (duplicate-instance entries).
"""

from __future__ import annotations

import win32api
import win32event
import winerror

_MUTEX_NAME = "Local Voice - Single Instance Mutex"
_handle = None  # kept alive for the process lifetime (module-level so it is never garbage-collected)


def acquire() -> bool:
    """Returns True if this process holds the single-instance lock. Returns
    False if another instance already holds it -- the caller should exit
    immediately without starting the controller or hotkey listener."""
    global _handle
    _handle = win32event.CreateMutex(None, False, _MUTEX_NAME)
    return win32api.GetLastError() != winerror.ERROR_ALREADY_EXISTS
