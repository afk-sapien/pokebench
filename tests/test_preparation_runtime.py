import json
from types import SimpleNamespace

import pytest
from pokecore.gen1 import W_PARTY_COUNT, W_PARTY_MONS, W_PARTY_SPECIES

from pokeagent_bench.evaluation_catalog import load_catalog
from pokeagent_bench.preparation_runtime import (
    PreparationSession, RULES, load_submission, preparation_schema,
    request_submission, score_trials,
)


def fake_session(tmp_path):
    memory = bytearray(65536)
    memory[W_PARTY_COUNT] = 1
    memory[W_PARTY_SPECIES] = 177
    memory[W_PARTY_MONS] = 177
    memory[W_PARTY_MONS+2] = 10
    memory[W_PARTY_MONS+35] = 20
    memory[W_PARTY_MONS+33] = 15
    return SimpleNamespace(engine=SimpleNamespace(memory=memory, save=lambda: bytes(memory)),
                           output=tmp_path, scenario={}, frame=0, reason=None)


def test_every_preparation_catalog_task_has_runtime_contract():
    tasks = load_catalog('preparation')[0]['evals']
    assert {task['id'] for task in tasks} == set(RULES)
    for task in tasks:
        assert preparation_schema(task['id'])['properties']['actions']['maxItems'] == 40


@pytest.mark.parametrize('task,action', [
    ('preparation-lead-selection', {'operation': 'use_item', 'item': 20, 'slot': 0}),
    ('preparation-shop-for-challenge', {'operation': 'buy_item', 'item': 82, 'quantity': 1}),
    ('preparation-shop-for-challenge', {'operation': 'buy_item', 'item': 20, 'quantity': 1}),
    ('preparation-damaged-team-rescue', {'operation': 'use_item', 'item': 54, 'slot': 0}),
    ('preparation-scarce-tm-allocation', {'operation': 'teach_move', 'item': 224, 'slot': 0, 'forget': 0}),
    ('preparation-lead-selection', {'operation': 'reorder_party', 'first': True, 'second': 0}),
    ('preparation-lead-selection', {'operation': 'reorder_party', 'first': 0, 'second': 0, 'item': 20}),
])
def test_illegal_preparation_never_sends_controller_input(tmp_path, task, action):
    session = fake_session(tmp_path)
    before = session.engine.save()
    runtime = PreparationSession(session, task)
    with pytest.raises(ValueError):
        runtime.act(action)
    assert before == session.engine.save()


def test_submission_is_terminal_and_tampering_is_detected(tmp_path):
    runtime = PreparationSession(fake_session(tmp_path), 'preparation-lead-selection')
    destination = tmp_path / 'submission'
    runtime.submit(destination)
    assert load_submission(destination)['task_id'] == 'preparation-lead-selection'
    with pytest.raises(ValueError, match='already'):
        runtime.act({'operation': 'reorder_party', 'first': 0, 'second': 0})
    with pytest.raises(ValueError, match='already'):
        runtime.submit(tmp_path / 'again')
    (destination / 'submission.state').write_bytes(b'changed')
    with pytest.raises(ValueError, match='changed'):
        load_submission(destination)


def test_assessment_errors_are_not_failed_model_trials():
    rows = [{'trial_id': 0, 'completed': True},
            {'trial_id': 1, 'completed': False, 'evaluation_error': 'bad fixture'}]
    result = score_trials(rows, 2, .5)
    assert result['evaluation_errors'] == 1
    assert result['win_rate'] is None
    assert result['completed'] is None


def test_unvalidated_threshold_cannot_claim_pass_and_no_best_of_scoring():
    rows = [{'trial_id': i, 'completed': i < 2} for i in range(5)]
    assert score_trials(rows, 5)['completed'] is None
    assert score_trials(rows, 5, .8)['completed'] is False
    assert score_trials(rows, 5, .4)['completed'] is True
    with pytest.raises(ValueError):
        score_trials(rows[:1] * 5, 5, .8)


def test_preparation_provider_records_one_call_without_images():
    class Provider:
        server = None
        thread_id = None
        provider = 'codex'
        model = 'test-model'
        reasoning_effort = 'low'
        closed = False
        calls = 0

        def _start(self, deadline):
            self.thread_id = 'test-thread'

        def _complete(self, method, params, deadline):
            self.calls += 1
            assert all(item['type'] == 'text' for item in params['input'])
            return json.dumps({'actions': []}), {'input_tokens': 200, 'output_tokens': 10}

        def close(self):
            self.closed = True

    provider = Provider()
    task = load_catalog('preparation')[0]['evals'][0]
    result = request_submission(provider, task, {'party': [], 'bag': []}, 8000)
    assert result['usage']['input_tokens'] == 200
    assert result['budget_exceeded'] is False
    assert provider.closed and provider.calls == 1


def test_claude_transport_accepts_preparation_schema_without_gameplay_coercion():
    from collections import deque
    from pokeagent_bench.claude_provider import ClaudeCodeProvider
    from pokeagent_bench.preparation_runtime import normalize_preparation_response
    model = 'claude-sonnet-5-5'
    output = {'actions': [{'operation': 'reorder_party', 'first': 0, 'second': 1,
                          'item': None, 'slot': None, 'quantity': None, 'forget': None}]}
    events = deque([{'type': 'result', 'subtype': 'success', 'is_error': False,
                     'structured_output': output, 'modelUsage': {model: {
                         'inputTokens': 90, 'outputTokens': 40,
                         'cacheReadInputTokens': 0, 'cacheCreationInputTokens': 0}}}])
    provider = object.__new__(ClaudeCodeProvider)
    provider.model = model
    provider.total_usage = {}
    provider.schema = preparation_schema('preparation-lead-selection')
    provider.response_normalizer = normalize_preparation_response
    provider.server = SimpleNamespace(send=lambda event: None, event=lambda deadline: events.popleft())
    message, usage = provider._complete('turn/start', {'input': [{'type': 'text', 'text': 'Prepare'}]}, 10)
    assert json.loads(message) == output
    assert usage['input_tokens'] == 90
    assert provider.interface_record['correction_needed'] is False


def test_assessment_controller_recognizes_native_forced_switch_menu():
    from pokeagent_bench.preparation_runtime import FixedBattlePolicy
    view = {'party': [{'slot': 1, 'hp': 100}, {'slot': 2, 'hp': 0}],
            'battle': {'active_party_slot': 2},
            'screen': {'kind': 'menu', 'visible_choices': ['1: POLIWRATH', '2: KADABRA'],
                       'text': ['Bring out which', 'POKéMON?']}}
    assert FixedBattlePolicy().choose(view) == {
        'command': 'switch_pokemon', 'argument': '1', 'count': 1}


def test_fixed_policy_uses_gen1_effectiveness_and_immunity():
    from pokeagent_bench.preparation_runtime import FixedBattlePolicy
    policy = FixedBattlePolicy({'matchups': [[21, 5, 2], [21, 4, 2], [23, 4, 0]]})
    mon = {'slot': 1, 'level': 50, 'types': ['Water'], 'status': ['healthy']}
    surf = {'id': 57, 'power': 95, 'type': 'Water', 'accuracy_percent': 100, 'pp': 10}
    thunderbolt = {'id': 85, 'power': 95, 'type': 'Electric', 'accuracy_percent': 100, 'pp': 10}
    assert policy.move_value(mon, surf, ['Rock', 'Ground']) == 570
    assert policy.move_value(mon, thunderbolt, ['Rock', 'Ground']) == 0
    assert policy.move_value(mon, surf, ['Rock', 'Rock']) == 285
    assert policy.move_value(mon, {**surf, 'accuracy_percent': 50}, ['Rock']) == 142.5


def test_fixed_policy_switches_to_effective_replacement_then_observes_cooldown():
    from pokeagent_bench.preparation_runtime import FixedBattlePolicy
    policy = FixedBattlePolicy({'matchups': [[21, 5, 2], [21, 4, 2], [23, 4, 0]],
        'species': {'34': {'name': 'ONIX', 'types': [5, 4]}}})
    def mon(slot, kind, move):
        return {'slot': slot, 'hp': 100, 'max_hp': 100, 'level': 50, 'types': [kind],
                'status': ['healthy'], 'moves': [{'id': move, 'slot': 1, 'pp': 10,
                'type': kind, 'power': 95, 'accuracy_percent': 100}]}
    view = {'party': [mon(1, 'Electric', 85), mon(2, 'Water', 57)], 'bag': [],
            'battle': {'active_party_slot': 1, 'visible_hud': ['ONIX', '50']},
            'screen': {'kind': 'battle_menu', 'visible_choices': [], 'text': []}}
    assert policy.choose(view)['argument'] == '2'
    view['battle']['active_party_slot'] = 2
    assert policy.choose(view)['command'] == 'use_move'
    assert policy.turn - policy.last_switch < 3


def test_fixed_policy_does_not_use_dream_eater_on_awake_opponent():
    from pokeagent_bench.preparation_runtime import FixedBattlePolicy
    policy = FixedBattlePolicy()
    move = {'id': 138, 'power': 100, 'type': 'Psychic', 'pp': 10, 'accuracy_percent': 100}
    assert policy.move_value({'types': []}, move, []) == 0
    assert policy.move_value({'types': []}, move, [], asleep=True) == 100



@pytest.mark.parametrize('text,answer', [
    ('Delete an older move to make room for HYPER BEAM?', 'NO'),
    ('Abandon learning HYPER BEAM?', 'YES'),
    ('Will ASH change POKEMON?', 'NO'),
])
def test_assessment_keeps_submitted_moves_without_looping(text, answer):
    from pokeagent_bench.preparation_runtime import FixedBattlePolicy
    view = {'party': [{'slot': 1, 'hp': 40}], 'battle': {},
            'screen': {'kind': 'menu', 'visible_choices': ['YES', 'NO'], 'text': [text]}}
    assert FixedBattlePolicy().choose(view) == {'command': 'choose', 'argument': answer, 'count': 1}


def test_assessment_does_not_spam_amnesia_against_physical_opponent():
    from pokeagent_bench.preparation_runtime import FixedBattlePolicy
    policy = FixedBattlePolicy({'species': {'1': {'name': 'HITMONLEE', 'types': [1, 1]}}})
    view = {'party': [{'slot': 1, 'hp': 200, 'max_hp': 200, 'types': ['Normal'],
                      'status': ['healthy'], 'moves': [
                          {'id': 133, 'slot': 1, 'pp': 20, 'power': 0, 'type': 'Psychic'},
                          {'id': 34, 'slot': 2, 'pp': 15, 'power': 85, 'type': 'Normal'}]}],
            'bag': [], 'battle': {'visible_hud': ['HITMONLEE']},
            'screen': {'kind': 'battle_menu', 'visible_choices': [], 'text': []}}
    assert policy.choose(view)['argument'] == '2'


def test_between_battle_maintenance_requires_owned_resources():
    from pokeagent_bench.preparation_runtime import between_battle_item
    mon = {'slot': 1, 'hp': 0, 'max_hp': 100, 'moves': [], 'status': ['healthy']}
    view = {'party': [mon], 'bag': []}
    assert between_battle_item(view) is None
    view['bag'] = [{'id': 53, 'quantity': 1}, {'id': 18, 'quantity': 1}]
    assert between_battle_item(view)['argument'] == 'Revive:1'
    mon['hp'] = 50
    view['bag'] = [{'id': 18, 'quantity': 1}]
    assert between_battle_item(view)['argument'] == 'Hyper Potion:1'
    mon['hp'] = 100
    assert between_battle_item(view) is None


def test_fixed_capture_requires_initial_encounter_and_rejects_escape():
    from pokeagent_bench.catalog_runtime import CatalogEvaluator
    from test_catalog_runtime import state, observe
    facts = state()
    facts['party'] = facts['party'][:1]
    objective = {'kind': 'catalog-task', 'task_id': 'objectives-capture-pikachu-fixed', 'description': 'Capture'}
    with pytest.raises(ValueError, match='live initial'):
        CatalogEvaluator(facts, objective)
    facts.update(battle=1, enemy_species=84, overworld=False)
    ev = CatalogEvaluator(facts, objective)
    facts.update(battle=0, overworld=True)
    assert not observe(ev, facts)
    assert ev.disqualified


def test_assessment_restores_key_attack_pp_before_using_weak_backup():
    from pokeagent_bench.preparation_runtime import FixedBattlePolicy, between_battle_item
    policy = FixedBattlePolicy({'matchups': [[23, 21, 2], [23, 2, 2], [1, 2, .5]],
                               'species': {'1': {'name': 'GYARADOS', 'types': [21, 2]}}})
    mon = {'slot': 1, 'hp': 100, 'max_hp': 100, 'types': ['Electric'], 'status': ['healthy'],
           'moves': [{'id': 85, 'slot': 1, 'pp': 0, 'power': 95, 'type': 'Electric'},
                     {'id': 24, 'slot': 2, 'pp': 30, 'power': 30, 'type': 'Fighting'}]}
    view = {'party': [mon], 'bag': [{'id': 82, 'quantity': 1}],
            'battle': {'visible_hud': ['GYARADOS']},
            'screen': {'kind': 'battle_menu', 'visible_choices': [], 'text': []}}
    assert policy.choose(view)['argument'] == 'Elixer:1'
    assert between_battle_item(view)['argument'] == 'Elixer:1'
    view['bag'] = []
    assert between_battle_item(view) is None
    assert policy.choose(view)['command'] == 'use_move'
