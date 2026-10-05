from pokeagent_bench.core import Limits
from pokeagent_bench.providers import ProviderError
from pokeagent_bench.runner import run
from pokeagent_bench.session import Session


class StubProvider:
    provider = "openai"
    model = "test"

    def __init__(self, decision=None, error=None):
        self.decision = decision
        self.error = error

    def decide(self, *args):
        if self.error:
            raise self.error
        return self.decision, {"input_tokens": 10, "output_tokens": 5}, {}

    def close(self):
        pass


def test_call_budget_and_usage_are_persisted(tmp_path, engine):
    session = Session(engine, tmp_path / "run", {}, limits=Limits(max_model_calls=2))
    provider = StubProvider({"button": "wait", "hold_frames": 2, "release_frames": 0, "notes": "plan"})
    result = run(session, provider, input_price=1, output_price=2)
    assert result["stop_reason"] == "model_call_budget"
    assert result["frames"] == 4
    assert result["usage"]["input_tokens"] == 20
    assert result["usage"]["estimated_cost_usd"] == 0.00004
    assert engine.closed


def test_repeated_invalid_output_does_not_advance_game(session):
    result = run(session, StubProvider({"button": "rewind"}))
    assert result["stop_reason"] == "invalid_model_response"
    assert result["actions"] == 0
    assert result["usage"]["calls"] == 3


def test_provider_failure_is_not_a_gameplay_failure(session):
    result = run(session, StubProvider(error=ProviderError("HTTP 429")))
    assert result["stop_reason"] == "provider_error"
    assert result["score"] == 0
    assert result["usage"]["calls"] == 1


def test_reported_token_budget_stops_before_more_gameplay(tmp_path, engine):
    session = Session(engine, tmp_path / "run", {}, limits=Limits(max_total_tokens=20))
    provider = StubProvider({"button": "wait", "hold_frames": 2, "release_frames": 0, "notes": None})
    result = run(session, provider)
    assert result["stop_reason"] == "token_budget"
    assert result["usage"]["calls"] == 2
    assert result["usage"]["input_tokens"] + result["usage"]["output_tokens"] == 30
    assert result["frames"] == 2
    assert result["token_budget"]["enforcement"] == "reported-between-decisions"


def test_missing_usage_stops_without_free_actions(session):
    class NoUsage(StubProvider):
        def decide(self, *args):
            return {"button": "wait", "hold_frames": 1, "release_frames": 0, "notes": None}, {}, {}
    result = run(session, NoUsage())
    assert result["stop_reason"] == "usage_unavailable"
    assert result["actions"] == 0
    assert result["usage"]["accounting_complete"] is False


def test_batch_uses_one_model_call_and_stops_on_success(tmp_path, engine):
    def award(emu):
        emu.state['badges'] = 1
        emu.state['gym_flags'][0] = True
    engine.on_tick = award
    session = Session(engine, tmp_path / 'batch', {}, limits=Limits(max_model_calls=1))
    result = run(session, StubProvider({'actions': [
        {'button': 'wait', 'hold_frames': 2, 'release_frames': 0},
        {'button': 'a', 'hold_frames': 10, 'release_frames': 10}], 'notes': None}))
    assert result['completed']
    assert result['actions'] == 1
    assert result['usage']['calls'] == 1
    assert engine.inputs == []


def test_invalid_later_batch_action_rejects_whole_batch(session):
    result = run(session, StubProvider({'actions': [
        {'button': 'a', 'hold_frames': 8, 'release_frames': 8},
        {'button': 'teleport', 'hold_frames': 8, 'release_frames': 8}], 'notes': None}))
    assert result['stop_reason'] == 'invalid_model_response'
    assert result['actions'] == result['frames'] == 0


def test_estimated_next_request_stops_before_spending_more(tmp_path, engine):
    class ReservedProvider(StubProvider):
        next_decision_token_estimate = None
        def decide(self, *args):
            self.next_decision_token_estimate = 15
            return super().decide(*args)
    session = Session(engine, tmp_path / 'reserved', {}, limits=Limits(max_total_tokens=20))
    result = run(session, ReservedProvider({'button': 'wait', 'hold_frames': 2, 'release_frames': 0, 'notes': None}))
    assert result['usage']['calls'] == 1
    assert result['stop_reason'] == 'token_budget'
    assert result['frames'] == 2


def test_batch_respects_total_frame_budget(tmp_path, engine):
    session = Session(engine, tmp_path / 'batch-budget', {}, limits=Limits(max_frames=5))
    result = run(session, StubProvider({'actions': [
        {'button': 'wait', 'hold_frames': 3, 'release_frames': 0},
        {'button': 'wait', 'hold_frames': 3, 'release_frames': 0},
        {'button': 'a', 'hold_frames': 3, 'release_frames': 0}], 'notes': None}))
    assert result['stop_reason'] == 'frame_budget'
    assert result['frames'] == 5
    assert result['actions'] == 2
    assert result['usage']['calls'] == 1


def test_batch_cannot_exceed_configured_length(tmp_path, engine):
    session = Session(engine, tmp_path / 'short-batch', {}, limits=Limits(max_actions_per_decision=1))
    result = run(session, StubProvider({'actions': [
        {'button': 'a', 'hold_frames': 3, 'release_frames': 0},
        {'button': 'a', 'hold_frames': 3, 'release_frames': 0}], 'notes': None}))
    assert result['stop_reason'] == 'invalid_model_response'
    assert result['frames'] == 0


def test_area_budget_stops_despite_changing_pixels_and_positions(tmp_path, engine):
    import json
    session = Session(engine, tmp_path / "area", {}, limits=Limits(max_area_tokens=30))
    result = run(session, StubProvider({"button": "wait", "hold_frames": 2, "release_frames": 0, "notes": None}))
    assert result["stop_reason"] == "area_token_budget"
    assert result["usage"]["calls"] == 2
    assert result["frames"] == 4
    assert json.loads((session.output / "area_budget.json").read_text())["tokens_in_area"] == 30


def test_area_change_resets_budget_including_exit_at_threshold(tmp_path, engine):
    import json

    def change_map(emu):
        if emu.frame == 4:
            emu.state["map_id"] = 1

    engine.on_tick = change_map
    session = Session(engine, tmp_path / "exit", {}, limits=Limits(max_area_tokens=30))
    result = run(session, StubProvider({"button": "wait", "hold_frames": 2, "release_frames": 0, "notes": None}))
    assert result["stop_reason"] == "area_token_budget"
    assert result["usage"]["calls"] == 4
    state = json.loads((session.output / "area_budget.json").read_text())
    assert state["map_id"] == 1
    assert state["entry_tokens"] == 30
    assert state["tokens_in_area"] == 30


def test_completion_takes_priority_over_area_budget(tmp_path, engine):
    def award(emu):
        emu.state["badges"] = 1
        emu.state["gym_flags"][0] = True

    engine.on_tick = award
    session = Session(engine, tmp_path / "win-area", {}, limits=Limits(max_area_tokens=15))
    result = run(session, StubProvider({"button": "wait", "hold_frames": 2, "release_frames": 0, "notes": None}))
    assert result["completed"]
    assert result["stop_reason"] == "completed"


def test_disabled_area_budget_preserves_existing_limits(tmp_path, engine):
    session = Session(engine, tmp_path / "disabled-area", {}, limits=Limits(max_model_calls=3))
    result = run(session, StubProvider({"button": "wait", "hold_frames": 2, "release_frames": 0, "notes": None}))
    assert result["stop_reason"] == "model_call_budget"
    assert not (session.output / "area_budget.json").exists()
