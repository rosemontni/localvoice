import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from local_voice.config import Settings, _validate


def test_defaults_round_trip_through_validate():
    validated = _validate({})
    assert validated == vars(Settings())


def test_unknown_keys_are_dropped():
    validated = _validate({"hotkey": "f10", "made_up_field": 123})
    assert validated["hotkey"] == "f10"
    assert "made_up_field" not in validated


def test_type_mismatch_falls_back_to_default():
    validated = _validate({"recording_limit_seconds": "not-a-number"})
    assert validated["recording_limit_seconds"] == Settings().recording_limit_seconds
