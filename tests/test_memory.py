import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from local_voice import memory


def test_too_similar_detects_shared_distinctive_words():
    assert memory._too_similar("马友友 -- 大提琴家 (cellist)", "马友友 -- 著名大提琴家")


def test_too_similar_false_for_unrelated_facts():
    assert not memory._too_similar("马友友 -- 大提琴家 (cellist)", "Project Aurora -- Q3 deadline")


def test_load_facts_missing_file_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(memory, "MEMORY_PATH", tmp_path / "memory.json")
    assert memory.load_facts() == []


def test_load_facts_corrupt_file_returns_empty(tmp_path, monkeypatch):
    path = tmp_path / "memory.json"
    path.write_text("not json", encoding="utf-8")
    monkeypatch.setattr(memory, "MEMORY_PATH", path)
    assert memory.load_facts() == []


def test_save_then_load_round_trips(tmp_path, monkeypatch):
    monkeypatch.setattr(memory, "MEMORY_PATH", tmp_path / "memory.json")
    memory.save_facts(["马友友 -- 大提琴家 (cellist)", "Project Aurora -- Q3 deadline"])
    assert memory.load_facts() == ["马友友 -- 大提琴家 (cellist)", "Project Aurora -- Q3 deadline"]


def test_load_facts_caps_at_max_facts(tmp_path, monkeypatch):
    monkeypatch.setattr(memory, "MEMORY_PATH", tmp_path / "memory.json")
    many = [f"fact {i}" for i in range(memory.MAX_FACTS + 10)]
    memory.save_facts(many)
    assert len(memory.load_facts()) == memory.MAX_FACTS
