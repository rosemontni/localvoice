"""System tray entry point: launch/quit from the Windows tray instead of a
console window. This is the packaged-app entry point (see scripts/run_tray.py,
intended to run under pythonw.exe so no console flashes); scripts/run_console.py
remains for development/debugging with visible logs.
"""

from __future__ import annotations

import logging
import os
import threading
import time

import pystray
from PIL import Image, ImageDraw

from ._version import __version__
from .config import RUNTIME_ROOT, load_settings
from .controller import Controller, State
from .hotkey import HotkeyListener
from .logging_setup import LOG_PATH, setup_logging
from .single_instance import acquire as acquire_single_instance_lock
from .updater import check_now, maybe_check_once_per_day

logger = logging.getLogger("local_voice.tray")

_STATE_COLORS = {
    State.STARTING: (128, 128, 128),
    State.LOADING: (66, 133, 244),  # blue
    State.READY: (52, 168, 83),  # green
    State.RECORDING: (219, 68, 55),  # red
    State.TRANSCRIBING: (244, 180, 0),  # amber
    State.UNAVAILABLE: (128, 128, 128),
}


def _state_image(state: State) -> Image.Image:
    color = _STATE_COLORS.get(state, (128, 128, 128))
    size = 64
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((4, 4, size - 4, size - 4), fill=color)
    return image


def _open_folder(path) -> None:
    try:
        os.startfile(path)  # noqa: S606 -- opening a local folder the app itself owns, not user-controlled input
    except OSError:
        logger.exception("could not open folder: %s", path)


def _notify_already_running() -> None:
    # This process never creates a pystray Icon (nothing to run() and pump a
    # message loop for), so it can't use icon.notify() -- a plain native
    # message box is the simplest way to actually tell the user what
    # happened, instead of silently exiting with only a log line.
    import ctypes

    ctypes.windll.user32.MessageBoxW(
        0,
        "Local Voice is already running.\n\nCheck your system tray (including the hidden-icons overflow area, the ^ arrow next to the clock) for its icon.",
        "Local Voice",
        0x40,  # MB_ICONINFORMATION
    )


def main() -> None:
    logger_root = setup_logging()
    if not acquire_single_instance_lock():
        logger_root.warning("another instance is already running; exiting without starting a second one")
        _notify_already_running()
        return
    settings = load_settings()
    logger_root.info("local-voice %s starting (tray)", __version__)

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

    def _status_text(_item) -> str:
        extra = f" ({controller.unavailable_reason})" if controller.state is State.UNAVAILABLE else ""
        return f"Status: {controller.state.name}{extra}"

    def _check_updates(icon: pystray.Icon, _item=None) -> None:
        result = check_now()
        if result:
            icon.notify(f"Local Voice {result['version']} is available: {result['url']}", title="Update available")
        else:
            icon.notify("You're on the latest version.", title="Local Voice")

    def _quit(icon: pystray.Icon, _item=None) -> None:
        controller.on_quit()
        icon.stop()

    icon = pystray.Icon(
        "LocalVoice",
        icon=_state_image(State.STARTING),
        title="Local Voice",
        menu=pystray.Menu(
            pystray.MenuItem(_status_text, None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Check for updates", _check_updates),
            pystray.MenuItem("Open logs folder", lambda icon, item: _open_folder(LOG_PATH.parent)),
            pystray.MenuItem("Open settings folder", lambda icon, item: _open_folder(RUNTIME_ROOT)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", _quit),
        ),
    )

    def _watch_state() -> None:
        last_state: State | None = None
        shown_ready_notification = False
        while not controller.quit_requested:
            if controller.state != last_state:
                last_state = controller.state
                try:
                    icon.icon = _state_image(controller.state)
                    icon.title = f"Local Voice — {controller.state.name}"
                    if controller.state is State.READY and not shown_ready_notification:
                        shown_ready_notification = True
                        icon.notify(f"Ready — hold {settings.hotkey.upper()} to dictate.", title="Local Voice")
                    elif controller.state is State.UNAVAILABLE:
                        icon.notify(f"Failed to start: {controller.unavailable_reason}", title="Local Voice")
                except Exception:
                    logger.exception("failed to update tray icon; continuing")
            time.sleep(0.2)
        icon.stop()

    def _startup_update_check() -> None:
        if not settings.check_for_updates:
            return
        result = maybe_check_once_per_day()
        if result:
            icon.notify(f"Local Voice {result['version']} is available: {result['url']}", title="Update available")

    def _on_icon_ready(icon: pystray.Icon) -> None:
        # Runs once the icon actually exists in the shell (pystray's
        # documented hook for this) -- calling icon.notify() any earlier
        # risks racing the icon's own registration. This is the "yes,
        # something happened" signal for the first few seconds while the
        # model is still loading, before the tray icon's own color change
        # is something anyone would think to go looking for.
        icon.visible = True
        icon.notify("Starting up — loading the speech model, this takes a few seconds...", title="Local Voice")
        threading.Thread(target=_watch_state, daemon=True).start()
        threading.Thread(target=_startup_update_check, daemon=True).start()

    try:
        icon.run(setup=_on_icon_ready)  # blocks this thread until icon.stop() (Quit, or state-watch loop noticing quit_requested)
    finally:
        listener.stop()
        controller.shutdown()


if __name__ == "__main__":
    main()
