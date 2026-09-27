"""Windows automatic-paste delivery (M2).

Sends exactly one Ctrl+V via SendInput, and only when the foreground window
captured at recording start is still the foreground window, and no modifier
key is unexpectedly held. Never elevates to reach a higher-privilege window;
never retries a paste attempt (that could produce duplicate output). The
clipboard write always happens first and is never undone here, so manual
paste remains available regardless of what happens in this module.
See docs/ARCHITECTURE.md ("Windows text delivery") and
docs/VALIDATION_PLAN.md's mandatory delivery cases.
"""

from __future__ import annotations

import ctypes
import logging
from ctypes import wintypes

import win32gui
import win32process

logger = logging.getLogger("local_voice.paste")

_user32 = ctypes.WinDLL("user32", use_last_error=True)

_INPUT_KEYBOARD = 1
_KEYEVENTF_KEYUP = 0x0002
_VK_CONTROL = 0x11
_VK_MENU = 0x12  # Alt
_VK_SHIFT = 0x10
_VK_LWIN = 0x5B
_VK_RWIN = 0x5C
_VK_V = 0x56

ForegroundTarget = tuple[int, int]  # (hwnd, pid)


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),  # real Win32 type is ULONG_PTR: a pointer-*sized integer*, not an actual pointer
    ]


class _MOUSEINPUT(ctypes.Structure):
    # Never populated: this field exists only so ctypes computes the same
    # union size Windows expects (the real INPUT union is sized by its
    # largest member, MOUSEINPUT, not KEYBDINPUT -- 40 bytes on x64, not 32).
    # Omitting it makes SendInput reject every call with ERROR_INVALID_PARAMETER (87).
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [("ki", _KEYBDINPUT), ("mi", _MOUSEINPUT)]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("ii", _INPUT_UNION)]


_user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(_INPUT), ctypes.c_int)
_user32.SendInput.restype = wintypes.UINT


def _send_key(vk: int, key_up: bool) -> bool:
    ki = _KEYBDINPUT(wVk=vk, wScan=0, dwFlags=(_KEYEVENTF_KEYUP if key_up else 0), time=0, dwExtraInfo=0)
    inp = _INPUT(type=_INPUT_KEYBOARD, ii=_INPUT_UNION(ki=ki))
    sent = _user32.SendInput(1, ctypes.pointer(inp), ctypes.sizeof(inp))
    if sent != 1:
        logger.warning("SendInput rejected vk=0x%02x key_up=%s (GetLastError=%s)", vk, key_up, ctypes.get_last_error())
        return False
    return True


def _send_ctrl_v_once() -> bool:
    ok = True
    ok &= _send_key(_VK_CONTROL, False)
    ok &= _send_key(_VK_V, False)
    ok &= _send_key(_VK_V, True)
    ok &= _send_key(_VK_CONTROL, True)
    return bool(ok)


def _unexpected_modifier_held() -> bool:
    for vk in (_VK_CONTROL, _VK_MENU, _VK_SHIFT, _VK_LWIN, _VK_RWIN):
        if _user32.GetAsyncKeyState(vk) & 0x8000:
            return True
    return False


def get_foreground_target() -> ForegroundTarget | None:
    """(hwnd, pid) of the current foreground window, or None if there isn't
    one or the window changed/closed between the two Win32 calls below."""
    try:
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return None
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        return hwnd, pid
    except Exception:
        logger.warning("could not read the foreground window", exc_info=True)
        return None


def try_auto_paste(expected_target: ForegroundTarget | None) -> bool:
    """Send one Ctrl+V iff the foreground window is still `expected_target`
    (captured at recording start) and no modifier is unexpectedly held.
    Returns whether the paste was actually sent. The clipboard text is
    untouched either way, so nothing is lost if this returns False."""
    if expected_target is None:
        return False
    if get_foreground_target() != expected_target:
        logger.info("auto-paste skipped: foreground target changed since recording started")
        return False
    if _unexpected_modifier_held():
        logger.info("auto-paste skipped: a modifier key is currently held")
        return False
    ok = _send_ctrl_v_once()
    if ok:
        logger.info("auto-paste sent (Ctrl+V)")
    else:
        logger.warning("auto-paste failed: SendInput rejected one or more key events; text remains on the clipboard")
    return ok
