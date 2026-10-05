import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from pokeagent_bench.codex_provider import CodexProvider
from pokeagent_bench.providers import ProviderError


def mock_process(monkeypatch, events, status="Logged in using ChatGPT"):
    calls = []
    def run(command, **kwargs):
        if "exec" in command:
            instruction_arg = next(arg for arg in command if arg.startswith("model_instructions_file="))
            instruction_path = Path(json.loads(instruction_arg.split("=", 1)[1]))
            assert instruction_path.read_text() == CodexProvider.prompt
        if "exec" in command:
            kwargs["captured_image"] = Path(command[command.index("--image") + 1]).read_bytes()
            kwargs["captured_schema"] = json.loads(Path(command[command.index("--output-schema") + 1]).read_text())
        calls.append((command, kwargs))
        output = status if "login" in command else "codex-cli 0.147.0" if "--version" in command else "\n".join(
            json.dumps(event) for event in events)
        return SimpleNamespace(returncode=0, stdout=output, stderr="")
    monkeypatch.setattr("pokeagent_bench.codex_provider.subprocess.run", run)
    return calls


def events():
    return [{"type": "item.completed", "item": {"type": "agent_message", "text": json.dumps(
        {"actions": [{"button": "a", "hold_frames": 1, "release_frames": 1}], "notes": None})}},
        {"type": "turn.completed", "usage": {"input_tokens": 100, "cached_input_tokens": 50, "output_tokens": 20}}]


def test_subscription_adapter_uses_schema_image_and_isolated_decision(session, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "not-to-be-used")
    monkeypatch.setenv("CODEX_APP_TOOLS_PIPE_PATH", "/not-for-benchmark")
    monkeypatch.setenv("CODEX_THREAD_ID", "parent-task")
    calls = mock_process(monkeypatch, events())
    provider = CodexProvider("explicit-test-model")
    decision, usage, record = provider.decide(session.observe(), "", [], session.limits, 30)
    assert decision["actions"][0]["button"] == "a"
    assert usage["input_tokens"] == 100
    assert provider.next_decision_token_estimate == 632
    command, options = calls[-1]
    assert "--ignore-user-config" in command and "--ephemeral" in command
    assert "--image" in command and "--output-schema" in command
    assert "shell_tool" in command and "multi_agent" in command
    assert "OPENAI_API_KEY" not in options["env"]
    assert "CODEX_APP_TOOLS_PIPE_PATH" not in options["env"]
    assert "CODEX_THREAD_ID" not in options["env"]
    assert "plugins" in command and "apps" in command and "personality" in command
    assert "You are playing" not in options["input"]
    assert options["timeout"] == 30
    assert "recent_actions" in options["input"]
    assert record["cli_version"] == "codex-cli 0.147.0"
    assert "response" not in record


def test_codex_refuses_api_login(monkeypatch):
    mock_process(monkeypatch, [], status="Logged in using an API key")
    with pytest.raises(ValueError, match="ChatGPT"):
        CodexProvider("test")


def test_codex_outside_tools_are_not_scored(session, monkeypatch):
    output = events()
    output.insert(0, {"type": "item.started", "item": {"type": "command_execution"}})
    mock_process(monkeypatch, output)
    with pytest.raises(ProviderError, match="outside tool"):
        CodexProvider("test").decide(session.observe(), "", [], session.limits, 30)


def test_codex_missing_completion_fails_closed(session, monkeypatch):
    mock_process(monkeypatch, events()[:1])
    with pytest.raises(ProviderError, match="complete"):
        CodexProvider("test").decide(session.observe(), "", [], session.limits, 30)


def test_codex_receives_exact_screen_strip_and_typed_notebook(session, monkeypatch):
    import base64
    from pokeagent_bench.visual_feedback import VisualFeedback
    calls = mock_process(monkeypatch, events())
    provider = CodexProvider("explicit-test-model")
    observation = session.observe()
    observation["status"]["track"] = "visual"
    observation["game"] = {"secret": "MUST_NOT_REACH_MODEL"}
    view = VisualFeedback(session.output).prepare(observation, 1)
    observation["controller_view"] = view
    notes = {"observed": ["Initial screen"], "hypotheses": [],
             "unsuccessful_attempts": [], "next_experiment": "Look for an exit"}
    _, _, record = provider.decide(observation, json.dumps(notes), [], session.limits, 30)
    options = calls[-1][1]
    assert options["captured_image"] == base64.b64decode(view["base64"])
    assert "MUST_NOT_REACH_MODEL" not in options["input"]
    assert json.loads(options["input"])["notes"] == notes
    assert record["presentation"]["image_sha256"] == view["image_sha256"]
    assert "base64" not in record["presentation"]
    note_schema = options["captured_schema"]["properties"]["notes"]["anyOf"][1]
    assert set(note_schema["required"]) == set(notes)
