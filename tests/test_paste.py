import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from local_voice import paste


def test_no_paste_when_expected_target_is_none():
    assert paste.try_auto_paste(None) is False


def test_no_paste_when_foreground_target_changed(monkeypatch):
    monkeypatch.setattr(paste, "get_foreground_target", lambda: (999, 1234))
    sent = []
    monkeypatch.setattr(paste, "_send_ctrl_v_once", lambda: (sent.append(True), True)[1])
    assert paste.try_auto_paste((111, 222)) is False
    assert sent == []


def test_no_paste_when_a_modifier_is_held(monkeypatch):
    monkeypatch.setattr(paste, "get_foreground_target", lambda: (111, 222))
    monkeypatch.setattr(paste, "_unexpected_modifier_held", lambda: True)
    sent = []
    monkeypatch.setattr(paste, "_send_ctrl_v_once", lambda: (sent.append(True), True)[1])
    assert paste.try_auto_paste((111, 222)) is False
    assert sent == []


def test_pastes_exactly_once_when_target_unchanged_and_no_modifier_held(monkeypatch):
    monkeypatch.setattr(paste, "get_foreground_target", lambda: (111, 222))
    monkeypatch.setattr(paste, "_unexpected_modifier_held", lambda: False)
    sent = []
    monkeypatch.setattr(paste, "_send_ctrl_v_once", lambda: (sent.append(True), True)[1])
    assert paste.try_auto_paste((111, 222)) is True
    assert sent == [True]


def test_returns_false_when_send_input_is_rejected(monkeypatch):
    monkeypatch.setattr(paste, "get_foreground_target", lambda: (111, 222))
    monkeypatch.setattr(paste, "_unexpected_modifier_held", lambda: False)
    monkeypatch.setattr(paste, "_send_ctrl_v_once", lambda: False)
    assert paste.try_auto_paste((111, 222)) is False
