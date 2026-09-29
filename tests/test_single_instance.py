import sys
from pathlib import Path

import win32api
import win32event

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from local_voice import single_instance


def test_acquire_detects_a_lock_already_held_by_another_instance():
    # Hold the named mutex ourselves first, via an independent handle (not
    # single_instance's own module-level one), to simulate another instance
    # already running -- acquire() must then report the lock as unavailable.
    blocking_handle = win32event.CreateMutex(None, False, single_instance._MUTEX_NAME)
    try:
        assert single_instance.acquire() is False
    finally:
        win32api.CloseHandle(blocking_handle)
