from copy import deepcopy
from types import SimpleNamespace

import pytest

from pokeagent_bench import suite
from pokeagent_bench.suite_report import summarize
from pokesim_core.gen1 import W_IS_IN_BATTLE, W_TRAINER_CLASS


def test_nine_tasks_and_budget_are_registered_without_changing_older_suites(monkeypatch):
    assert len(suite.DEFINITION['tasks']) == 5
    assert len(suite.EXPANDED_DEFINITION['tasks']) == 6
    definition = suite.definition_for('red-ability-v1')
    assert len(definition['tasks']) == 9
    assert len({task['id'] for task in definition['tasks']}) == 9
    monkeypatch.setattr(suite, 'validate', lambda *args: {'definition': definition})
    plan = suite.plan('.', ['luna', 'terra', 'sol'], 1)
    assert len(plan['cells']) == 27
    assert plan['maximum_tokens'] == 25_500_000


def test_ranking_requires_matching_full_coverage_and_preserves_ties():
    definition = {**suite.DEFINITION, 'tasks': suite.TASKS[:1]}
    cells = [{'id': str(i), 'model': name, 'task': 'starter', 'repeat': 1,
              'status': 'finished', 'tokens': tokens, 'replay': {'verified': True},
              'result': {'completed': passed}}
             for i, (name, tokens, passed) in enumerate([('luna', 10, False), ('terra', 5, True), ('sol', 2, True)])]
    batch = {'cells': cells, 'models': ['luna','terra','sol'], 'phase': 'finished',
             'budget': 100, 'configuration': {}}
    report = summarize(batch, definition)
    assert report['ranking_ready']
    assert {m['model']:m['rank'] for m in report['models']} == {'sol':1, 'terra':1, 'luna':3}
    for status in ['running','pending','error']:
        partial = deepcopy(batch)
        partial['cells'][0]['status'] = status
        report = summarize(partial, definition)
        assert not report['ranking_ready']
        assert all(m['rank'] is None for m in report['models'])


@pytest.mark.parametrize('task_id,trainer', [('agatha',46),('lance',47),('lorelei',44),('bruno',33),('champion-duel',43)])
def test_elite_segment_rejects_wrong_opponent_and_earned_flag(monkeypatch, task_id, trainer):
    task = next(t for t in [*suite.SKILL_TASKS, *suite.NEW_SKILL_TASKS] if t['id'] == task_id)
    memory = {W_IS_IN_BATTLE: 2, W_TRAINER_CLASS: trainer}
    progress = {'elite': {task_id.title():False}, 'hall_of_fame':0, 'champion':False}
    engine = SimpleNamespace(memory=memory, evidence=lambda:progress)
    monkeypatch.setattr('pokeagent_bench.gameplay.ui_state', lambda memory: {'kind':'battle_menu'})
    suite.check_start(task, engine)
    memory[W_TRAINER_CLASS] = 1
    with pytest.raises(ValueError):
        suite.check_start(task, engine)
    memory[W_TRAINER_CLASS] = trainer
    if task_id == 'champion-duel':
        progress['champion'] = True
    else:
        progress['elite'][task_id.title()] = True
    with pytest.raises(ValueError):
        suite.check_start(task, engine)


def test_five_new_tasks_have_separate_budgets_and_do_not_mutate_live_suite(monkeypatch):
    original = deepcopy(suite.ABILITY_DEFINITION)
    new = suite.definition_for('red-skills-v1')
    expanded = suite.definition_for('red-ability-v2')
    assert {t['id'] for t in new['tasks']} == {'first-capture', 'parcel-delivery', 'lorelei', 'bruno', 'champion-duel'}
    assert len({t['id'] for t in expanded['tasks']}) == 14
    assert expanded['tasks'][:9] == original['tasks']
    monkeypatch.setattr(suite, 'validate', lambda *args: {'definition': new})
    planned = suite.plan('.', ['luna', 'terra', 'sol'], 1)
    assert len(planned['cells']) == 15
    assert planned['maximum_tokens'] == 10_500_000
    assert suite.ABILITY_DEFINITION == original


def test_capture_checkpoint_rejects_missing_supplies_or_wrong_battle(monkeypatch):
    task = suite.NEW_SKILL_TASKS[0]
    facts = {'party_count': 1, 'owned': [7], 'balls': 10, 'battle': 1, 'battle_type': 0}
    engine = SimpleNamespace(memory={}, challenge_evidence=lambda objective: facts,
                             evidence=lambda: {'story': {'pokedex': True}})
    monkeypatch.setattr('pokeagent_bench.gameplay.ui_state', lambda memory: {'kind': 'battle_menu'})
    suite.check_start(task, engine)
    for key, value in [('balls', 0), ('party_count', 2), ('battle', 2), ('battle_type', 1)]:
        old = facts[key]
        facts[key] = value
        with pytest.raises(ValueError, match='First capture'):
            suite.check_start(task, engine)
        facts[key] = old


def test_delivery_checkpoint_requires_viridian_and_undelivered_parcel(monkeypatch):
    task = suite.NEW_SKILL_TASKS[1]
    facts = {'parcel': 1, 'parcel_delivered': False, 'battle': 0}
    progress = {'map_id': 1}
    engine = SimpleNamespace(memory={}, challenge_evidence=lambda objective: facts, evidence=lambda: progress)
    monkeypatch.setattr('pokeagent_bench.gameplay.ui_state', lambda memory: {'kind': 'overworld'})
    suite.check_start(task, engine)
    for key, value in [('parcel', 0), ('parcel_delivered', True), ('battle', 1)]:
        old = facts[key]
        facts[key] = value
        with pytest.raises(ValueError, match='Parcel delivery'):
            suite.check_start(task, engine)
        facts[key] = old
    progress['map_id'] = 40
    with pytest.raises(ValueError, match='Parcel delivery'):
        suite.check_start(task, engine)
