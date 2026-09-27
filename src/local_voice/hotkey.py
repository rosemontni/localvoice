"""Global push-to-talk key plus cancel/quit keys, via pynput.

No tray exists yet (that is M4), so this console build binds fixed
auxiliary keys for cancel and quit. The push-to-talk key itself is the one
open "which hotkey" decision from docs/DECISIONS_AND_RISKS.md and is read
from settings so it can be changed without touching code.
"""

from __future__ import annotations

import logging
from typing import Callable

from pynput import keyboard

logger = logging.getLogger("local_voice.hotkey")

CANCEL_KEY = keyboard.Key.esc
QUIT_KEY = keyboard.Key.f12


def resolve_key(name: str) -> keyboard.Key | keyboard.KeyCode:
    name = name.strip().lower()
    special = getattr(keyboard.Key, name, None)
    if special is not None:
        return special
    if len(name) == 1:
        return keyboard.KeyCode.from_char(name)
    raise ValueError(f"unrecognized hotkey name: {name!r}")


class HotkeyListener:
    def __init__(
        self,
        ptt_key_name: str,
        on_ptt_down: Callable[[], None],
        on_ptt_up: Callable[[], None],
        on_cancel: Callable[[], None],
        on_quit: Callable[[], None],
    ) -> None:
        self._ptt_key = resolve_key(ptt_key_name)
        self._on_ptt_down = on_ptt_down
        self._on_ptt_up = on_ptt_up
        self._on_cancel = on_cancel
        self._on_quit = on_quit
        self._ptt_held = False  # debounce repeated key-down while held
        self._listener: keyboard.Listener | None = None

    def _on_press(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        # This runs on pynput's low-level keyboard-hook thread. An exception
        # escaping here would propagate into that hook callback, which is
        # exactly the kind of thing that can destabilize the process -- so
        # every callback invocation is isolated, never allowed to raise.
        try:
            if key == self._ptt_key:
                if not self._ptt_held:
                    self._ptt_held = True
                    self._on_ptt_down()
                return
            if key == CANCEL_KEY:
                self._on_cancel()
                return
            if key == QUIT_KEY:
                self._on_quit()
        except Exception:
            logger.exception("hotkey on_press callback failed; ignoring and continuing")

    def _on_release(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        try:
            if key == self._ptt_key and self._ptt_held:
                self._ptt_held = False
                self._on_ptt_up()
        except Exception:
            logger.exception("hotkey on_release callback failed; ignoring and continuing")

    def start(self) -> None:
        self._listener = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
        self._listener.start()
        logger.info("hotkey listener started (ptt=%s, cancel=Esc, quit=F12)", self._ptt_key)

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None

    def is_ptt_held(self) -> bool:
        """Used by Controller's recording-cap watchdog to decide whether to
        auto-restart a new chunk (key still down) or just stop."""
        return self._ptt_held
