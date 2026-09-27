"""Sanitized logging: stages, timings, versions, errors only.

Never pass transcript text, audio, clipboard, or vocabulary contents to these
loggers, per docs/REQUIREMENTS.md P05.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from .config import RUNTIME_ROOT

LOG_PATH = RUNTIME_ROOT / "logs" / "app.log"


def setup_logging() -> logging.Logger:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("local_voice")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    file_handler = RotatingFileHandler(LOG_PATH, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    console_handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    for handler in (file_handler, console_handler):
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger
