"""Settings load/save for Local Voice.

Runtime data lives outside the OneDrive-synced source workspace, per
docs/REQUIREMENTS.md P03 and docs/ARCHITECTURE.md.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

SCHEMA_VERSION = 1

RUNTIME_ROOT = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "LocalVoice"
SETTINGS_PATH = RUNTIME_ROOT / "settings.json"


@dataclass
class Settings:
    schema_version: int = SCHEMA_VERSION
    microphone: str = "default"  # "default" = OS default recording device, queried at startup
    hotkey: str = "f9"  # provisional default; see docs/DECISIONS_AND_RISKS.md, still open for change
    language: str = "auto"  # "auto" | "en" | "zh"
    mode: str = "literal"  # "literal" | "grammar" (narrow grammar-only fix, see cleanup.py) | "clean" (full M3 rewrite, not yet implemented)
    model_size: str = "large-v3"  # switched from large-v3-turbo 2026-09-26; see docs/DECISIONS_AND_RISKS.md
    device: str = "cuda"
    compute_type: str = "float16"
    recording_limit_seconds: int = 120
    history_enabled: bool = False
    history_retention: str = "7d"  # "24h" | "7d" | "never"
    vocabulary: list[str] = field(default_factory=list)  # recognition hints (faster-whisper `hotwords`); no exact-match guarantee, per REQUIREMENTS.md F09
    auto_paste: bool = False  # M2: one Ctrl+V via SendInput if the foreground target hasn't changed; clipboard fallback always remains
    persistent_context: bool = True  # bounded, abstracted standing facts (memory.py) that survive restarts; see docs/DECISIONS_AND_RISKS.md
    check_for_updates: bool = True  # narrow exception to the offline-by-default policy; at most once/day automatically, see updater.py


def _validate(data: dict) -> dict:
    defaults = asdict(Settings())
    validated = dict(defaults)
    for key, value in data.items():
        if key not in defaults:
            continue  # drop unknown keys rather than fail load
        if not isinstance(value, type(defaults[key])):
            continue  # keep default on type mismatch
        validated[key] = value
    return validated


def load_settings() -> Settings:
    if not SETTINGS_PATH.exists():
        settings = Settings()
        save_settings(settings)
        return settings
    try:
        raw = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return Settings()
    return Settings(**_validate(raw))


def save_settings(settings: Settings) -> None:
    RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
    tmp_path = SETTINGS_PATH.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")
    os.replace(tmp_path, SETTINGS_PATH)  # atomic on Windows for same-volume renames
