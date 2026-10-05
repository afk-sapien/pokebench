from copy import deepcopy
import json

import pytest

from pokeagent_bench.bounded_context import build, check_size, render, state
from pokeagent_bench.bounded_provider import BoundedGameplayProvider
from pokeagent_bench.codex_provider import CodexProvider
from pokeagent_bench.core import Limits, digest
from pokeagent_bench.recovery import resume
from pokeagent_bench.runner import run
from pokeagent_bench.session import Session
from pokeagent_bench.visual_feedback import VisualFeedback
from test_continuous import Server, events
from test_readable_context import payload
from test_recovery_memory import factory
from test_runner import StubProvider


def public():
    value = payload()['observation']
    value['frame'] = 8
    return value


def apply(packet, previous):
    result = {'game': {}, 'agent': {}} if packet['kind'] == 'snapshot' else deepcopy(previous)
    for path in packet['remove']:
        group, key = path.split('.', 1)
        del result[group][key]
    for group, fields in packet['replace'].items():
        result[group].update(deepcopy(fields))
    return result


def test_updates_reconstruct_full_state_and_distinguish_empty_removed_and_null():
    obs = public()
    packet, baseline = build(obs, 'Persistent notes', [], None, 1, 1)
    assert apply(packet, None) == baseline == state(obs, 'Persistent notes')
    changed = deepcopy(obs)
    changed['game']['party'] = [{'name': 'Example', 'hp': 3}]
    changed['game']['battle'] = None
    changed['game']['bag'] = []
    del changed['game']['local_map']
    changed['game']['screen'] = {'visible_choices': []}
    delta, current = build(changed, None, [], baseline, 2, 1)
    assert delta['kind'] == 'update' and delta['base_sequence'] == 1
    assert 'game.local_map' in delta['remove']
    assert delta['replace']['game']['battle'] is None
    assert 'bag' not in delta['replace']['game']
    assert delta['replace']['agent']['notes'] is None
    assert apply(delta, baseline) == current
    assert 'recall' not in delta and 'task' not in delta
    assert 'working_memory' not in render(delta)


def test_handoff_preserves_agent_memory_and_bounds_observed_recall():
    obs = public()
    working = obs['game']['memory']['working_memory']
    entry = working['recent_decisions'][0]
    working['recent_decisions'] = [{**entry, 'decision': n} for n in range(50)]
    packet, _ = build(obs, 'Keep this uncertainty', [], None, 52, 4)
    assert packet['base_sequence'] is None
    assert packet['replace']['agent']['notes'] == 'Keep this uncertainty'
    assert packet['replace']['agent']['plan'] == obs['game']['memory']['agent_plan']
    recall = packet['recall']
    assert 0 < len(recall['recent_decisions']) <= 8
    assert recall['omitted_decisions'] == 50 - len(recall['recent_decisions'])
    assert recall['recent_decisions'][-1]['decision'] == 49
    assert render(packet) == render(json.loads(json.dumps(packet, sort_keys=True)))


def test_private_fields_and_raw_controller_feedback_are_not_forwarded():
    obs = public()
    obs['private_evaluator'] = 'PRIVATE_SENTINEL'
    obs['game']['secret_quest_flag'] = 'PRIVATE_SENTINEL'
    packet, _ = build(obs, '', [{'button': 'a', 'raw': 'PRIVATE_SENTINEL'}, {'error': 'Bad action'}], None, 1, 1)
    assert 'PRIVATE_SENTINEL' not in render(packet)
    assert packet['controller_errors'] == [{'error': 'Bad action'}]


def test_oversize_observation_is_rejected_before_any_model_call(tmp_path, engine):
    class TooLarge(StubProvider):
        def estimate_next_tokens(self, *args):
            check_size({}, 'x' * 32001)
        def decide(self, *args):
            pytest.fail('Oversized observation must not reach the model')
    session = Session(engine, tmp_path / 'oversized', {})
    result = run(session, TooLarge())
    assert result['stop_reason'] == 'observation_budget'
    assert result['usage']['calls'] == result['actions'] == 0
    assert result['usage']['accounting_complete']
    assert not (session.output / 'pending.json').exists()


def test_budget_admission_uses_actual_preflight_instead_of_stale_estimate(tmp_path, engine):
    class Preflight(StubProvider):
        next_decision_token_estimate = 999999
        def estimate_next_tokens(self, *args):
            return 5
    session = Session(engine, tmp_path / 'preflight', {}, limits=Limits(max_model_calls=1, max_total_tokens=100))
    result = run(session, Preflight())
    assert result['usage']['calls'] == 1


@pytest.fixture
def bounded(monkeypatch):
    def initialize(self, model, **kwargs):
        self.model = model
        self.reasoning_effort = 'low'
        self.cli_version = 'test'
    monkeypatch.setattr(CodexProvider, '__init__', initialize)
    return BoundedGameplayProvider('test-model', context_turns=2)


def test_segment_reset_is_free_and_next_call_contains_checkpoint(bounded, monkeypatch, session):
    servers = []
    def start(deadline):
        bounded.thread_id = 'thread'
        bounded.server = Server(events(total=100) + events(total=200))
        servers.append(bounded.server)
    monkeypatch.setattr(bounded, '_start', start)
    obs = session.observe()
    obs['status']['track'] = 'gameplay'
    obs['status']['max_dialogue_frames'] = session.limits.max_dialogue_frames
    obs['game'] = public()['game']
    obs['controller_view'] = VisualFeedback(session.output, current_only=True).prepare(obs, 1)
    received = []
    for _ in range(3):
        decision, _, record = bounded.decide(obs, 'My plan notes', [], session.limits, 20)
        assert decision['actions']
        received.append(record)
    assert len(servers) == 2
    assert [r['model_context']['kind'] for r in received] == ['snapshot', 'update', 'snapshot']
    assert [r['segment'] for r in received] == [1, 1, 2]
    assert sum(len(server.requests) for server in servers) == 3
    assert bounded.compactions == 0
    assert not any(r.get('maintenance') == 'compaction' for r in received)
    assert received[-1]['model_context']['replace']['agent']['notes'] == 'My plan notes'
    assert session.frame == 0
    for server in servers:
        for _, request in server.requests:
            assert 'summary' not in request['outputSchema']['properties']


def test_observed_context_threshold_rotates_before_next_request(bounded):
    obs = {'frame': 1, 'status': {'track': 'gameplay', 'goal': 'challenge', 'emulated_seconds': 0,
           'remaining': {}, 'token_budget': {}, 'max_action_frames': 600, 'max_actions_per_decision': 1,
           'max_note_bytes': 2048, 'max_dialogue_frames': 7200}, 'game': public()['game']}
    bounded.packet_baseline = state(public(), '')
    bounded.context_tokens = bounded.compact_at
    bounded.packet_sequence = 5
    bounded.segment_index = 1
    _, packet, _, _, rotate = bounded.prepare_packet(obs, '', [])
    assert rotate and packet['kind'] == 'snapshot' and packet['segment'] == 2


def test_packet_state_survives_runner_pause_resume(tmp_path, engine):
    class Stateful(StubProvider):
        def __init__(self):
            super().__init__()
            self.packet_baseline = {'game': {'map': 'observed'}, 'agent': {'notes': 'agent claim'}}
            self.packet_sequence = 0
            self.segment_turns = 0
            self.segment_index = 1
            self.seen = []
        def decide(self, *args):
            self.seen.append((deepcopy(self.packet_baseline), self.packet_sequence, self.segment_turns))
            self.packet_sequence += 1
            self.segment_turns += 1
            return super().decide(*args)
    rom = tmp_path / 'fake.gb'
    rom.write_bytes(b'fake')
    session = Session(engine, tmp_path / 'resume', {'rom_sha256': digest(rom.read_bytes())}, limits=Limits(max_model_calls=2))
    first = Stateful()
    run(session, first, pause_after_decisions=1)
    restored = resume(rom, session.output, engine_factory=factory)
    second = Stateful()
    second.packet_baseline = None
    run(restored, second)
    assert second.seen[0] == (first.packet_baseline, 1, 1)


@pytest.mark.parametrize('look_back', [None, 1])
def test_empty_decision_keeps_usage_and_does_not_advance_game(bounded, monkeypatch, session, look_back):
    stream = events(total=100)
    stream[1]['params']['item']['text'] = json.dumps({
        'actions': [], 'notes': 'I think I am done', 'goal_plan': None, 'look_back': look_back})
    def start(deadline):
        bounded.thread_id = 'thread'
        bounded.server = Server(stream)
    monkeypatch.setattr(bounded, '_start', start)
    obs = session.observe()
    obs['status']['track'] = 'gameplay'
    obs['status']['max_dialogue_frames'] = session.limits.max_dialogue_frames
    obs['game'] = public()['game']
    obs['controller_view'] = VisualFeedback(session.output, current_only=True).prepare(obs, 1)
    decision, usage, record = bounded.decide(obs, '', [], session.limits, 20)
    assert decision['actions'] == []
    assert usage['input_tokens'] == 100 and usage['output_tokens'] == 10
    assert record.get('maintenance') == ('look_back' if look_back else None)
    assert bounded.packet_sequence == 1
    assert session.frame == 0


def test_empty_decisions_stop_as_model_errors_with_complete_accounting(tmp_path, engine):
    class Empty(StubProvider):
        def decide(self, *args):
            return {'actions': [], 'notes': None}, {'input_tokens': 100, 'output_tokens': 10}, {}
    session = Session(engine, tmp_path/'empty', {}, limits=Limits(max_model_calls=5))
    result = run(session, Empty())
    assert result['stop_reason'] == 'invalid_model_response'
    assert result['usage']['calls'] == 3
    assert result['usage']['input_tokens'] == 300
    assert result['usage']['output_tokens'] == 30
    assert result['usage']['accounting_complete']
    assert result['frames'] == result['actions'] == 0
