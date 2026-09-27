"""M1 console entry point: hotkey -> local transcript -> clipboard.

No tray/UI yet (that is M4). This prints state changes to the console so the
flow is observable while testing by hand.

Controls: hold the configured push-to-talk key (default F9) and speak,
release to transcribe and copy to the clipboard. Esc cancels a
recording/transcription in progress. F12 quits.
"""

from __future__ import annotations

import multiprocessing as mp
import time

from .config import load_settings
from .controller import Controller, State
from .hotkey import HotkeyListener
from .logging_setup import setup_logging


def main() -> None:
    logger = setup_logging()
    settings = load_settings()
    logger.info("settings loaded: hotkey=%s language=%s mode=%s microphone=%s", settings.hotkey, settings.language, settings.mode, settings.microphone)

    controller = Controller(settings)
    controller.start()

    listener = HotkeyListener(
        ptt_key_name=settings.hotkey,
        on_ptt_down=controller.on_ptt_down,
        on_ptt_up=controller.on_ptt_up,
        on_cancel=controller.on_cancel,
        on_quit=controller.on_quit,
    )
    listener.start()
    controller.set_ptt_held_probe(listener.is_ptt_held)

    print(f"Local Voice (M1 console build). Hold [{settings.hotkey.upper()}] to talk, release to copy to clipboard.", flush=True)
    print("Esc = cancel current job. F12 = quit. Loading model...", flush=True)

    last_state: State | None = None
    try:
        while not controller.quit_requested:
            try:
                if controller.state != last_state:
                    last_state = controller.state
                    extra = f" ({controller.unavailable_reason})" if controller.state is State.UNAVAILABLE else ""
                    print(f"[state] {controller.state.name}{extra}", flush=True)
                    if controller.state is State.UNAVAILABLE:
                        break
            except Exception:
                logger.exception("main loop tick failed; continuing")
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nCtrl+C received, shutting down...")
    finally:
        listener.stop()
        controller.shutdown()
        print("Stopped.", flush=True)


if __name__ == "__main__":
    mp.freeze_support()
    main()
