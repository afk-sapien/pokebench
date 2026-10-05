import json

import httpx
import pytest

from pokeagent_bench.core import Limits
from pokeagent_bench.providers import APIProvider, ProviderError

CHOICE = {"button": "a", "hold_frames": 8, "release_frames": 2, "notes": None}


@pytest.mark.parametrize("provider", ["openai", "anthropic"])
def test_provider_uses_image_and_one_action_without_leaking_key(provider, monkeypatch, session):
    monkeypatch.setenv("OPENAI_API_KEY", "private-test-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "private-test-key")
    captured = []

    def respond(request):
        captured.append(json.loads(request.content))
        if provider == "openai":
            return httpx.Response(200, json={"output": [{"type": "function_call", "name": "choose_action",
                                                        "arguments": json.dumps(CHOICE)}],
                                            "usage": {"input_tokens": 10, "output_tokens": 5}})
        return httpx.Response(200, json={"content": [{"type": "tool_use", "name": "choose_action", "input": CHOICE}],
                                        "usage": {"input_tokens": 10, "output_tokens": 5}})
    adapter = APIProvider(provider, "test-model", client=httpx.Client(transport=httpx.MockTransport(respond)))
    decision, usage, record = adapter.decide(session.observe(), "test notes", [], Limits(), 10)
    assert decision == CHOICE
    assert usage["input_tokens"] == 10
    assert "private-test-key" not in json.dumps(record)
    assert "test notes" in json.dumps(captured)
    assert "image" in json.dumps(captured)
    assert "gym_flags" not in json.dumps(captured)
    adapter.close()


def test_provider_error_does_not_record_response_body_or_key(monkeypatch, session):
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    client = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(401, text="secret")))
    provider = APIProvider("openai", "test", client=client)
    with pytest.raises(ProviderError, match="HTTP 401") as error:
        provider.decide(session.observe(), "", [], Limits(), 1)
    assert "secret" not in str(error.value)
    provider.close()


def test_missing_credentials_fail_before_a_run(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        APIProvider("openai", "test")
