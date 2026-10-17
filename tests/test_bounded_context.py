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
from test_continuous import Server, events as raw_events
from test_readable_context import payload
from test_recovery_memory import factory
from test_runner import StubProvider


def events(**kwargs):
    result = raw_events(**kwargs)
    item = result[1]['params']['item']
    if item.get('type') == 'agentMessage':
        value = json.loads(item['text'])
        value['actions'] = [{'command': 'wait', 'argument': '', 'count': 60}]
        item['text'] = json.dumps(value)
    return result


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
    for update in packet.get('party_updates', []):
        mon = result['game']['party'][update['slot'] - 1]
        mon.update(deepcopy(update['replace']))
        for key in update['remove']:
            del mon[key]
        for change in update.get('move_updates', []):
            move = next(m for i, m in enumerate(mon['moves'], 1) if m.get('slot', i) == change['slot'])
            move.update(deepcopy(change['replace']))
            for key in change['remove']:
                del move[key]
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


def test_on_demand_keeps_move_identity_and_pp_and_inspection_returns_full_details():
    obs = public()
    move = {'slot': 1, 'name': 'Example', 'pp': 7, 'type': 'Water', 'power': 40,
            'accuracy_percent': 100, 'effect': 'public effect', 'base_pp': 25, 'id': 9}
    obs['game']['party'] = [{'slot': 1, 'hp': 21, 'max_hp': 30, 'status': ['healthy'], 'moves': [move]}]
    original = deepcopy(obs)
    packet, baseline = build(obs, None, [], None, 1, 1, detail='on-demand')
    current = baseline['game']['party'][0]
    assert current['hp'] == 21 and current['status'] == ['healthy']
    assert current['moves'] == [{'slot': 1, 'name': 'Example', 'pp': 7, 'type': 'Water'}]
    assert 'Inspect party' in packet['inspection_help']
    assert obs == original
    obs['game']['inspection'] = {'topic': 'party', 'data': obs['game']['party']}
    next_packet, _ = build(obs, None, [], baseline, 2, 1, detail='on-demand')
    assert next_packet['requested_inspection']['data'][0]['moves'][0] == move


def test_invalid_detail_policy_rejected():
    with pytest.raises(ValueError, match='detail'):
        build(public(), None, [], None, 1, 1, detail='hidden-state')


def test_missing_metadata_is_normalized_without_a_paid_repair(bounded, monkeypatch, session):
    stream = events(total=100)
    stream[1]['params']['item']['text'] = json.dumps({'actions': [{'command': 'press', 'argument': 'a', 'count': 1}]})
    def start(deadline):
        bounded.thread_id = 'thread'
        bounded.server = Server(stream)
    monkeypatch.setattr(bounded, '_start', start)
    obs = session.observe()
    obs['status']['track'] = 'gameplay'
    obs['game'] = public()['game']
    obs['controller_view'] = VisualFeedback(session.output, current_only=True).prepare(obs, 1)
    decision, usage, _ = bounded.decide(obs, '', [], session.limits, 20)
    assert decision['notes'] is None and decision['goal_plan'] is None
    assert decision['actions'][0]['command'] == 'press'
    assert usage['input_tokens'] == 100


def test_malformed_json_preserves_usage_and_returns_zero_action_feedback(bounded, monkeypatch, session):
    stream = events(total=100)
    stream[1]['params']['item']['text'] = 'broken JSON'
    def start(deadline):
        bounded.thread_id = 'thread'
        bounded.server = Server(stream)
    monkeypatch.setattr(bounded, '_start', start)
    obs = session.observe()
    obs['status']['track'] = 'gameplay'
    obs['game'] = public()['game']
    obs['controller_view'] = VisualFeedback(session.output, current_only=True).prepare(obs, 1)
    decision, usage, record = bounded.decide(obs, '', [], session.limits, 20)
    assert decision['actions'] == [] and 'valid JSON' in decision['interface_error']
    assert usage['input_tokens'] == 100 and usage['output_tokens'] == 10
    assert record['response_validation_error'] == decision['interface_error']
    assert session.frame == 0


def test_party_deltas_preserve_moves_and_reconstruct_every_state():
    obs = public()
    obs['game']['party'] = [
        {'slot': 1, 'species': 'Charizard', 'nickname': 'One', 'hp': 80, 'status': ['healthy'],
         'moves': [{'slot': 1, 'id': 52, 'name': 'Ember', 'pp': 20, 'effect': 'Burn chance ' * 30},
                   {'slot': 3, 'id': 19, 'name': 'Fly', 'pp': 10, 'power': 70}]},
        {'slot': 2, 'species': 'Blastoise', 'nickname': 'Two', 'hp': 90, 'moves': []}]
    packet, baseline = build(obs, '', [], None, 1, 1)
    reconstructed = apply(packet, None)
    for sequence in range(2, 7):
        obs['game']['party'][0]['hp'] -= 5
        obs['game']['party'][0]['moves'][1]['pp'] -= 1
        packet, baseline = build(obs, '', [], baseline, sequence, 1)
        assert 'party' not in packet['replace']['game']
        assert 'Burn chance' not in render(packet)
        assert packet['party_updates'][0]['move_updates'][0]['slot'] == 3
        reconstructed = apply(packet, reconstructed)
        assert reconstructed == baseline == state(obs, '')
    # Changing a move replaces the complete moves list, including its description.
    obs['game']['party'][0]['moves'][0] = {'slot': 1, 'id': 53, 'name': 'Flamethrower', 'pp': 15}
    packet, baseline = build(obs, '', [], baseline, 7, 1)
    reconstructed = apply(packet, reconstructed)
    assert reconstructed == baseline
    obs['game']['party'].reverse()
    packet, baseline = build(obs, '', [], baseline, 8, 1)
    assert 'party' in packet['replace']['game']
    assert apply(packet, reconstructed) == baseline
    fresh, baseline = build(obs, '', [], None, 9, 2)
    assert apply(fresh, None) == baseline
    assert 'party_updates' not in fresh


def test_party_delta_removes_fields_and_empty_roster_replaces():
    obs = public()
    obs['game']['party'] = [{'slot': 1, 'nickname': 'One', 'hp': 5, 'status': []}]
    first, old = build(obs, '', [], None, 1, 1)
    del obs['game']['party'][0]['status']
    update, new = build(obs, '', [], old, 2, 1)
    assert update['party_updates'][0]['remove'] == ['status']
    assert apply(update, apply(first, None)) == new
    obs['game']['party'] = []
    update, empty = build(obs, '', [], new, 3, 1)
    assert apply(update, new) == empty


@pytest.mark.parametrize('provider_class,model', [
    (BoundedGameplayProvider, 'test-model'),
    (None, 'claude-sonnet-5-5'),
])
def test_current_screenshot_is_default_and_pair_is_explicit(provider_class, model, monkeypatch):
    from pokeagent_bench.claude_provider import ClaudeCodeProvider
    monkeypatch.setattr(CodexProvider, '_initialize_cli', lambda self: None)
    monkeypatch.setattr(ClaudeCodeProvider, '_initialize_cli', lambda self: None)
    provider_class = provider_class or ClaudeCodeProvider
    current = provider_class(model)
    pair = provider_class(model, presentation='before-after')
    assert current.current_only and not current.before_after
    assert pair.before_after and not pair.current_only
    assert not pair.compact_feedback
    assert pair.prompt == current.prompt
    assert pair.config_identity['presentation'] == 'before-after'
    assert current.config_identity['presentation'] == 'current'



def test_decision_allowance_survives_snapshot_and_delta():
    obs = public()
    obs['decision_budget'] = {'used': 0, 'remaining': 40, 'limit': 40}
    first, baseline = build(obs, '', [], None, 1, 1)
    assert first['decision_budget'] == obs['decision_budget']
    obs['decision_budget'] = {'used': 1, 'remaining': 39, 'limit': 40}
    second, _ = build(obs, '', [], baseline, 2, 1)
    assert second['decision_budget']['remaining'] == 39
    assert 'Decision budget:' in render(second)
    assert 'Remaining: 39' in render(second)


@pytest.mark.parametrize('remaining,expected', [(900, 600), (25, 25)])
def test_response_timeout_allows_slow_turn_but_respects_trial_deadline(
        bounded, monkeypatch, session, remaining, expected):
    import time
    before = time.monotonic()
    deadlines = []
    def start(deadline):
        deadlines.append(deadline)
        bounded.thread_id = 'thread'
        bounded.server = Server(events(total=100))
    monkeypatch.setattr(bounded, '_start', start)
    obs = session.observe()
    obs['status']['track'] = 'gameplay'
    obs['status']['max_dialogue_frames'] = session.limits.max_dialogue_frames
    obs['game'] = public()['game']
    obs['controller_view'] = VisualFeedback(session.output, current_only=True).prepare(obs, 1)
    bounded.decide(obs, '', [], session.limits, remaining)
    assert expected <= deadlines[0] - before < expected + 2
    assert bounded.config_identity['decision_timeout_seconds'] == 600
    assert len(bounded.server.requests) == 1


def test_large_inspection_uses_lossless_compact_encoding_without_mutation():
    obs = public()
    obs['game']['inspection'] = {'topic': 'memory', 'working_memory': {
        'recent_decisions': [{'decision': i, 'commands': [{'at': {'map_id': 3, 'x': i, 'y': 4},
            'after': {'map_id': 3, 'x': i, 'y': 5}, 'action': {'command': 'move', 'argument': 'up', 'count': 1},
            'outcome': 'Observed movement', 'encounter_id': None} for _ in range(2)]} for i in range(100)]}}
    packet, _ = build(obs, 'Keep my notes', [], None, 506, 64)
    original = deepcopy(packet)
    text = render(packet)
    marker = 'REQUESTED INSPECTION (compact JSON, all fields retained)\n'
    assert marker in text
    assert json.loads(text.split(marker)[1]) == obs['game']['inspection']
    assert packet == original
    assert 'Keep my notes' in text
    check_size(packet, text)


def test_small_inspection_keeps_readable_tree_and_oversized_data_still_stops():
    obs = public()
    obs['game']['inspection'] = {'topic': 'memory', 'dialogue': ['hello']}
    packet, _ = build(obs, '', [], None, 1, 1)
    assert 'compact JSON' not in render(packet)
    packet['requested_inspection']['dialogue'] = ['x' * 64001]
    with pytest.raises(ValueError, match='Observation text exceeds'):
        check_size(packet, render(packet))


@pytest.mark.parametrize('task_status', ['not_complete', 'complete'])
def test_completion_feedback_reaches_rendered_snapshots_and_updates(task_status):
    obs = public()
    obs['task_status'] = task_status
    previous = None
    for sequence in (1, 2):
        packet, previous = build(obs, 'I claim success', [], previous, sequence, 1)
        assert packet['task_status'] == task_status
        assert f'Task status: {task_status}' in render(packet)
        assert packet['protocol'] == 'bounded-gameplay-context-v3'


def test_visible_object_motion_and_blocked_feedback_reach_model_without_private_fields():
    obs = public()
    motion = [{'id': 'object-1', 'from': {'x': 4, 'y': 5}, 'to': {'x': 5, 'y': 5}}]
    obs['game']['last_command'] = {
        'outcome': 'Player position unchanged. Visible object positions changed.',
        'visible_object_changes': motion,
        'evaluator_target': 'PRIVATE_TARGET',
    }
    packet, previous = build(obs, '', [], None, 1, 1)
    assert packet['last_result']['visible_object_changes'] == motion
    assert 'Visible object changes:' in render(packet)
    assert 'PRIVATE_TARGET' not in render(packet)
    obs['game']['last_command'] = {
        'outcome': 'Moved 0 tiles, then blocked or no further movement.',
        'blocked_at': {'map_id': 108, 'x': 4, 'y': 5},
    }
    packet, _ = build(obs, '', [], previous, 2, 1)
    assert 'visible_object_changes' not in packet['last_result']
    assert 'Blocked at:' in render(packet)
