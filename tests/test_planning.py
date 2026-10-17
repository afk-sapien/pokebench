import json

import pytest

from pokeagent_bench.core import Limits, digest
from pokeagent_bench.planning import validate
from pokeagent_bench.runner import run
from pokeagent_bench.session import Session
from pokeagent_bench.recovery import resume
from test_recovery_memory import factory
from test_runner import StubProvider

PLAN = {"goal": "Explore elsewhere", "evidence": "Repeated interactions gave the same text",
        "done_when": "A new conversation or location is observed", "revision_reason": "Initial goal"}


class Planned(StubProvider):
    persistent_goal = True

    def __init__(self):
        self.calls = 0
        self.received = []

    def decide(self, observation, notes, *args):
        self.calls += 1
        return {"actions": [{"button": "wait", "hold_frames": 2, "release_frames": 0}],
                "notes": "New temporary instruction", "goal_plan": PLAN if self.calls == 1 else None}, {
                    "input_tokens": 10, "output_tokens": 5}, {}


def test_plan_survives_scratch_note_changes_and_pause_resume(tmp_path, engine):
    rom = tmp_path / 'fake.gb'
    rom.write_bytes(b'fake')
    session = Session(engine, tmp_path / 'run', {'rom_sha256': digest(rom.read_bytes())}, limits=Limits(max_model_calls=3))
    provider = Planned()
    run(session, provider, pause_after_decisions=1)
    original = dict(session.gameplay_memory['agent_plan'])
    restored = resume(rom, session.output, engine_factory=factory)
    final = run(restored, provider)
    assert final['usage']['calls'] == 3
    assert restored.gameplay_memory['agent_plan'] == original
    assert restored.notes == 'New temporary instruction'
    events = [json.loads(x) for x in (session.output / 'memory.jsonl').read_text().splitlines()]
    assert len([x for x in events if x['kind'] == 'agent_plan']) == 1


def test_invalid_action_does_not_commit_new_plan(tmp_path, engine):
    class Invalid(Planned):
        def decide(self, *args):
            decision, usage, record = super().decide(*args)
            decision['actions'][0]['button'] = 'teleport'
            decision['goal_plan'] = PLAN
            return decision, usage, record
    session = Session(engine, tmp_path / 'invalid', {})
    result = run(session, Invalid())
    assert result['stop_reason'] == 'invalid_model_response'
    assert 'agent_plan' not in session.gameplay_memory
    assert not session.actions


def test_plan_is_optional_but_supplied_plans_require_explicit_reason():
    assert validate(None, None) is None
    with pytest.raises(ValueError):
        validate(None, None, require_initial=True)
    assert validate(None, PLAN) is None
    with pytest.raises(ValueError):
        validate({**PLAN, 'revision_reason': ''}, PLAN)
    with pytest.raises(ValueError):
        validate({**PLAN, 'secret': 'hidden'}, PLAN)
    with pytest.raises(ValueError):
        validate({k: 'é' * 400 for k in PLAN}, PLAN)


@pytest.mark.parametrize("placeholder", ["null", " null ", ":null", "NONE", "n/a", "...", "keep"])
def test_placeholder_revision_is_not_evidence(placeholder):
    with pytest.raises(ValueError):
        validate({**PLAN, 'goal': 'A changed goal', 'revision_reason': placeholder}, PLAN)


def test_duplicate_plan_does_not_reset_age_or_add_revision(tmp_path, engine):
    from pokeagent_bench.planning import commit
    session = Session(engine, tmp_path / 'duplicates', {})
    session.current_decision = 1
    commit(session, validate(PLAN, None))
    original = dict(session.gameplay_memory['agent_plan'])
    session.current_decision = 2
    redundant = {**PLAN, 'goal': '  ' + PLAN['goal'] + '  ',
                 'revision_reason': 'Continuing the same experiment'}
    commit(session, validate(redundant, original))
    assert session.gameplay_memory['agent_plan'] == original
    assert not session.gameplay_memory.get('plan_revisions')


def test_evidence_update_is_still_an_explicit_revision():
    updated = {**PLAN, 'evidence': 'A new conversation rules out the previous assumption',
               'revision_reason': 'New dialogue changes the evidence for the goal'}
    assert validate(updated, PLAN) == updated


def test_non_ascii_plan_evidence_is_not_a_placeholder():
    plan = {**PLAN, 'evidence': '見える会話'}
    assert validate(plan, None) == plan


@pytest.mark.parametrize("include_plan", [False, True])
def test_initial_action_needs_no_plan_or_notes(tmp_path, engine, include_plan):
    decision = {"actions": [{"button": "wait", "hold_frames": 2, "release_frames": 0}]}
    if include_plan:
        decision["goal_plan"] = None
    provider = StubProvider(decision)
    provider.persistent_goal = True
    session = Session(engine, tmp_path / "optional-initial", {}, limits=Limits(max_model_calls=1))
    result = run(session, provider)
    assert result["stop_reason"] == "model_call_budget"
    assert result["frames"] == 2
    assert "agent_plan" not in session.gameplay_memory
    assert session.notes == ""
    assert "notes" not in decision


@pytest.mark.parametrize("include_metadata", [False, True])
def test_missing_or_null_metadata_retains_existing_plan_and_notes(tmp_path, engine, include_metadata):
    from pokeagent_bench.planning import commit

    session = Session(engine, tmp_path / "optional-existing", {}, limits=Limits(max_model_calls=1))
    session.current_decision = 0
    commit(session, validate(PLAN, None))
    original = dict(session.gameplay_memory["agent_plan"])
    session.write_notes("My own persistent notes")
    decision = {"actions": [{"button": "wait", "hold_frames": 2, "release_frames": 0}]}
    if include_metadata:
        decision.update(goal_plan=None, notes=None)
    provider = StubProvider(decision)
    provider.persistent_goal = True
    result = run(session, provider)
    assert result["frames"] == 2
    assert session.gameplay_memory["agent_plan"] == original
    assert session.notes == "My own persistent notes"
    events = [json.loads(line) for line in (session.output / "memory.jsonl").read_text().splitlines()]
    assert len([event for event in events if event["kind"] == "agent_plan"]) == 1


@pytest.mark.parametrize("bad_plan", ["null", {}, {**PLAN, "evidence": ""}])
def test_optional_plan_still_rejects_invalid_supplied_plan(tmp_path, engine, bad_plan):
    session = Session(engine, tmp_path / "bad-optional-plan", {})
    provider = StubProvider({"actions": [{"button": "wait", "hold_frames": 2, "release_frames": 0}],
                             "goal_plan": bad_plan})
    provider.persistent_goal = True
    result = run(session, provider)
    assert result["stop_reason"] == "invalid_model_response"
    assert result["frames"] == result["actions"] == 0
    assert "agent_plan" not in session.gameplay_memory
    assert result["usage"]["calls"] == 3


@pytest.mark.parametrize("metadata", [{"notes": None}, {"notes": None, "goal_plan": None}, {"goal_plan": PLAN}])
def test_legacy_required_planning_metadata_remains_available(tmp_path, engine, metadata):
    session = Session(engine, tmp_path / "legacy-required", {})
    provider = StubProvider({"actions": [{"button": "wait", "hold_frames": 2, "release_frames": 0}],
                             **metadata})
    provider.persistent_goal = True
    provider.required_planning_metadata = True
    result = run(session, provider)
    assert result["stop_reason"] == "invalid_model_response"
    assert result["frames"] == 0
    assert "agent_plan" not in session.gameplay_memory
