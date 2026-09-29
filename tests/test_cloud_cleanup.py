import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from local_voice import cloud_cleanup


class FakeClient:
    def __init__(self, response_text, raise_exc=None):
        self._response_text = response_text
        self._raise_exc = raise_exc
        self.last_kwargs = None
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.last_kwargs = kwargs
        if self._raise_exc:
            raise self._raise_exc
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=self._response_text)])


def test_returns_none_on_client_error(monkeypatch):
    monkeypatch.setattr(cloud_cleanup, "_get_client", lambda: FakeClient("", raise_exc=RuntimeError("missing API key")))
    assert cloud_cleanup.correct_grammar_cloud("he don't like it") is None


def test_strips_output_label_and_returns_corrected_text(monkeypatch):
    fake = FakeClient("Output: he doesn't like it")
    monkeypatch.setattr(cloud_cleanup, "_get_client", lambda: fake)
    result = cloud_cleanup.correct_grammar_cloud("he don't like it")
    assert result == "he doesn't like it"


def test_rejects_untrustworthy_output(monkeypatch):
    # drastically shorter than the input -> fails the length-ratio safety check
    fake = FakeClient("ok")
    monkeypatch.setattr(cloud_cleanup, "_get_client", lambda: fake)
    result = cloud_cleanup.correct_grammar_cloud("he don't like it because it was too expensive for us")
    assert result is None


def test_context_is_included_in_the_prompt(monkeypatch):
    fake = FakeClient("corrected text")
    monkeypatch.setattr(cloud_cleanup, "_get_client", lambda: fake)
    cloud_cleanup.correct_grammar_cloud("some text", context="马友友 -- cellist")
    prompt = fake.last_kwargs["messages"][0]["content"]
    assert "马友友" in prompt
    assert "some text" in prompt


def test_uses_the_requested_model(monkeypatch):
    fake = FakeClient("corrected text")
    monkeypatch.setattr(cloud_cleanup, "_get_client", lambda: fake)
    cloud_cleanup.correct_grammar_cloud("some text", model="claude-haiku-5-5-20260101")
    assert fake.last_kwargs["model"] == "claude-haiku-5-5-20260101"
