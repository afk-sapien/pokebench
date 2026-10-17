"""Task policy cannot be bypassed by provider transport or direct execution."""
import asyncio
import json

import pytest
from jsonschema import Draft202012Validator

from pokeagent_bench.action_policy import ASSISTED, MANUAL, from_manifest, resolve
from pokeagent_bench.bounded_provider import BoundedGameplayProvider
from pokeagent_bench.claude_provider import ClaudeCodeProvider
from pokeagent_bench.core import Limits
from pokeagent_bench.gameplay_commands import execute
from pokeagent_bench.gameplay_contract import COMMANDS, action_schema, validate_command
from pokeagent_bench.mcp_server import create_server
from pokeagent_bench.session import Session
from pokeagent_bench.visual_feedback import public_context
from test_gameplay import catalog, memory
from test_gameplay_contract import EXAMPLES, request


def manual_session(tmp_path, engine):
    engine.memory = memory()
    return Session(engine, tmp_path / "run", {"name": "item-recovery"}, track="gameplay",
                   gameplay_catalog=catalog(), limits=Limits(max_action_frames=60))


def test_resolution_and_historical_default():
    assert resolve({"name": "item-recovery"}) == MANUAL
    assert resolve({"task_id": "item-recovery", "name": "custom"}) == MANUAL
    assert resolve({"name": "item-recovery", "action_policy": ASSISTED}) == ASSISTED
    assert resolve({}, MANUAL) == MANUAL
    assert resolve({'name': 'buy-pokeballs'}) == MANUAL
    assert resolve({'name': 'new-task', 'tested_skill': 'menu-operation'}) == MANUAL
    assert resolve({'tested_skill': 'battle-strategy'}) == ASSISTED
    with pytest.raises(ValueError, match='Unsupported tested skill'):
        resolve({'tested_skill': 'typo'})
    for name in ("starter", "heal", "team-rescue", "recovery-detour", "league"):
        assert resolve({"name": name}) == ASSISTED
    assert from_manifest({"scenario": {"name": "item-recovery"}}) == ASSISTED
    assert from_manifest({"action_policy": MANUAL}) == MANUAL
    with pytest.raises(ValueError, match="Unsupported action policy"):
        resolve({}, "unknown")


@pytest.mark.parametrize("kind", COMMANDS)
def test_manual_schema_runtime_agree(kind):
    limits = Limits()
    value = request(kind, *EXAMPLES[kind])
    permitted = kind in ("press", "wait", "inspect")
    assert Draft202012Validator(action_schema(limits, MANUAL)).is_valid(value) == permitted
    if permitted:
        assert validate_command(value, limits, MANUAL) == value
    else:
        with pytest.raises(ValueError, match="disabled by manual-menu-v1"):
            validate_command(value, limits, MANUAL)


@pytest.mark.parametrize("provider_class", [BoundedGameplayProvider, ClaudeCodeProvider])
def test_providers_hide_shortcuts_and_explain_manual_controls(provider_class):
    provider = object.__new__(provider_class)
    provider.config_identity = {}
    provider.response_contract = "simple"
    provider.configure_action_policy(MANUAL)
    schema = provider.decision_schema(Limits())
    allowed = schema["properties"]["actions"]["items"]["anyOf"]
    assert {row["properties"]["command"]["enum"][0] for row in allowed} == {"press", "wait", "inspect"}
    assert "Manual menu task" in provider.prompt
    assert "Prefer these shortcuts" not in provider.prompt
    assert "advances confirmed continue-only dialogue" not in provider.prompt
    assert provider.config_identity["action_policy"] == MANUAL
    assert provider.config_identity["controller_timing"] == "manual-tap-8-hold-24-release-v1"
    provider.configure_action_policy(ASSISTED)
    assert "use_item:" in provider.prompt
    assert provider.config_identity["controller_timing"] == "core-shortcuts-v060"


def test_runtime_blocks_before_input_and_records_policy(tmp_path, engine):
    session = manual_session(tmp_path, engine)
    try:
        assert json.loads((session.output / "manifest.json").read_text())["action_policy"] == MANUAL
        assert public_context(session.observe())["action_policy"] == MANUAL
        assert public_context(session.observe())["tested_skill"] == "menu-operation"
        assert session.manifest["tested_skill"] == "menu-operation"
        for kind in ("use_item", "choose", "advance_dialogue", "interact", "use_move", "switch_pokemon", "move"):
            with pytest.raises(ValueError, match="disabled by manual-menu-v1"):
                execute(session, kind, request(kind, *EXAMPLES[kind]))
        assert session.frame == 0
        assert not engine.inputs
        assert session.gameplay_operations == {}
    finally:
        session.close()


def test_manual_press_never_settles_dialogue_or_sends_extra_inputs(tmp_path, engine, monkeypatch):
    session = manual_session(tmp_path, engine)
    def forbidden(*args, **kwargs):
        raise AssertionError("Automatic dialogue was invoked")
    monkeypatch.setattr("pokeagent_bench.gameplay_commands.settle_dialogue", forbidden)
    try:
        result = execute(session, "tap", request("press", "a"))
        assert session.frame == 32
        assert engine.inputs == [("press", "a", 0), ("release", "a", 8), ("release", "a", 32)]
        assert result["raw_actions"] == 1
        execute(session, "wait", request("wait", "", 10))
        assert session.frame == 42
        execute(session, "inspect", request("inspect", "party"))
        assert session.frame == 42
    finally:
        session.close()


def test_mcp_exposes_only_manual_commands_and_rejects_bypass(tmp_path, engine):
    session = manual_session(tmp_path, engine)
    async def check():
        server = create_server(session)
        tool = next(tool for tool in await server.list_tools() if tool.name == "gameplay_command")
        assert set(tool.inputSchema["properties"]["command"]["enum"]) == {"press", "wait", "inspect"}
        assert "Only press, wait and inspect" in tool.description
        with pytest.raises(Exception, match="press|disabled|validation"):
            await server.call_tool("gameplay_command", {"operation_id": "bypass", "command": "use_item", "argument": "Potion:1"})
        assert session.frame == 0 and not engine.inputs
    try:
        asyncio.run(check())
    finally:
        session.close()


@pytest.mark.parametrize("legacy", [False, True])
def test_resume_retains_frozen_policy_and_historical_default(tmp_path, legacy):
    from conftest import FakeEngine
    from pokeagent_bench.core import digest
    from pokeagent_bench.recovery import resume
    from pokeagent_bench.runner import run
    from test_recovery_memory import Provider, factory
    rom = tmp_path / "test.gb"
    rom.write_bytes(b"fake rom")
    session = Session(FakeEngine(), tmp_path / "run",
                      {"name": "item-recovery", "rom_sha256": digest(rom.read_bytes())},
                      track="visual", limits=Limits(max_model_calls=4), journal=True)
    if legacy:
        del session.manifest["action_policy"]
    run(session, Provider(), pause_after_decisions=1)
    restored = resume(rom, session.output, engine_factory=factory)
    try:
        assert restored.action_policy == (ASSISTED if legacy else MANUAL)
    finally:
        restored.close()


def test_report_separates_action_policies_and_exports_them(tmp_path):
    from conftest import FakeEngine
    from pokeagent_bench.paper_export import export_results
    from pokeagent_bench.report import read_runs, summarize
    for name, policy in (("manual", MANUAL), ("assisted", ASSISTED)):
        session = Session(FakeEngine(), tmp_path / name, {}, action_policy=policy)
        session.close()
    rows = read_runs(tmp_path)
    assert {row["action_policy"] for row in rows} == {ASSISTED, MANUAL}
    assert len({row["group"] for row in rows}) == 2
    assert len(summarize(rows)) == 2
    output = tmp_path / "report.json"
    export_results(tmp_path, output)
    assert {row["action_policy"] for row in json.loads(output.read_text())["runs"]} == {ASSISTED, MANUAL}
