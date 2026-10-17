import base64
import io
import json

import httpx
from PIL import Image
import pytest

from pokeagent_bench.core import Limits
from pokeagent_bench.jev_provider import ACTIONS, ENDPOINT, JevProvider, screen_png
from pokeagent_bench.providers import ProviderError
from pokeagent_bench.runner import run


def answer(choice="a", tokens=100):
    return {"model": "jev-1.14.0", "answers": {"action": {
        "type": "choice", "choice": choice, "confidence": 1,
        "probabilities": {key: float(key == choice) for key in ACTIONS}}},
        "usage": {"input_tokens": tokens}}


def client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_screens_are_scaled_without_smoothing(session):
    png = screen_png(base64.b64decode(session.observe()["screenshot"]["base64"]))
    assert Image.open(io.BytesIO(png)).size == (480, 432)


def test_image_request_is_multipart_and_maps_choice_to_one_press(session):
    seen = []

    def handle(request):
        assert str(request.url) == ENDPOINT
        data = request.read()
        assert data.index(b'name="request"') < data.index(b'name="current_screen"')
        seen.append(data)
        return httpx.Response(200, json=answer("up_long"))
    provider = JevProvider(client=client(handle))
    decision, usage, record = provider.decide(session.observe(), "", [], Limits(), 10)
    assert decision == {"button": "up", "hold_frames": 32, "release_frames": 16, "notes": None}
    assert usage == {"input_tokens": 100, "output_tokens": 0}
    assert record["choice"] == "up_long"
    assert b"Boulder Badge" in seen[0] and b"gym_flags" not in seen[0]
    # The second decision also sends the previous screen.
    provider.decide(session.observe(), "", [{"action": {"button": "a", "hold_frames": 8, "release_frames": 16}}], Limits(), 10)
    assert b'name="previous_screen"' in seen[1] and b'"button": "a"' in seen[1]


def test_wait_is_a_valid_buttonless_action(session):
    provider = JevProvider(client=client(lambda _: httpx.Response(200, json=answer("wait"))))
    decision, _, _ = provider.decide(session.observe(), "", [], Limits(), 10)
    assert decision["button"] == "wait" and decision["hold_frames"] >= 1


@pytest.mark.parametrize("change", [
    lambda p: p["answers"]["action"].update(choice="jump"),
    lambda p: p["answers"]["action"]["probabilities"].update(a=0.2),
    lambda p: p["usage"].update(input_tokens=-1),
    lambda p: p.pop("model"),
])
def test_invalid_responses_are_rejected(change, session):
    payload = answer()
    change(payload)
    provider = JevProvider(client=client(lambda _: httpx.Response(200, json=payload)))
    with pytest.raises(ProviderError, match="invalid action"):
        provider.decide(session.observe(), "", [], Limits(), 10)


def test_http_errors_hide_server_body(session):
    provider = JevProvider(client=client(lambda _: httpx.Response(401, text="secret body")))
    with pytest.raises(ProviderError, match="HTTP 401") as error:
        provider.decide(session.observe(), "", [], Limits(), 10)
    assert "secret" not in str(error.value)


def test_state_mode_sends_json_with_allowlisted_game_fields(session):
    observation = session.observe()
    observation["game"] = {"location": {"map_id": 0, "x": 1, "y": 2}}
    bodies = []

    def handle(request):
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json=answer())
    JevProvider(observation="state", client=client(handle)).decide(observation, "", [], Limits(), 10)
    assert bodies[0]["state"]["game_state"]["location"]["x"] == 1
    assert "assets" not in bodies[0] and "current_screen" not in bodies[0]["state"]


def test_state_mode_rejects_visual_track(session):
    observation = session.observe()
    observation.pop("game", None)
    provider = JevProvider(observation="state", client=client(lambda _: httpx.Response(200, json=answer())))
    with pytest.raises(ProviderError, match="structured or gameplay"):
        provider.decide(observation, "", [], Limits(), 10)


def test_missing_key_fails_before_a_run(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    with pytest.raises(ValueError, match="TYPESAFE_API_KEY"):
        JevProvider()


def test_runner_executes_jev_choices_and_counts_tokens(session, engine):
    session.limits = Limits(max_model_calls=2)
    choices = iter(["a", "down"])
    provider = JevProvider(client=client(lambda _: httpx.Response(200, json=answer(next(choices), 50))))
    result = run(session, provider)
    assert result["stop_reason"] == "model_call_budget"
    assert [row[1] for row in engine.inputs if row[0] == "press"] == ["a", "down"]
    assert session.usage["input_tokens"] == 100
    manifest = json.loads((session.output / "manifest.json").read_text())
    assert manifest["agent"]["provider"] == "jev" and manifest["agent"]["harness"] == "jev-choice-v1"
