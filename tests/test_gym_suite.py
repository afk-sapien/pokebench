from copy import deepcopy

import pytest
from pokesim_core.gen1 import W_IS_IN_BATTLE, W_TRAINER_CLASS

from conftest import blank_evidence
from pokeagent_bench import suite
from pokeagent_bench.challenges import ChallengeEvaluator
from pokeagent_bench.portal import category


def test_gym_sweep_preserves_existing_tasks_and_registers_equal_budgets(monkeypatch):
    definition = suite.definition_for('red-gyms-v1')
    assert len(definition['tasks']) == 9
    assert definition['tasks'][:2] == [suite.TASKS[-1], suite.ADVENTURE_TASKS[-1]]
    expanded = suite.definition_for('red-ability-v4')['tasks']
    assert len({task['id'] for task in expanded}) == 26
    assert expanded[:19] == suite.ABILITY_V3_DEFINITION['tasks']
    monkeypatch.setattr(suite, 'validate', lambda *args: {'definition': definition})
    plan = suite.plan('.', ['luna', 'terra', 'sol'], 1)
    assert len(plan['cells']) == 27
    assert plan['maximum_tokens'] == 26_250_000
    assert category(suite.HARD_LEAGUE_TASK) == 'Campaign'


@pytest.mark.parametrize('task', suite.GYM_TASKS, ids=lambda t: t['id'])
def test_gym_checkpoint_rejects_wrong_room_trainer_and_already_won(monkeypatch, task):
    from pokeagent_bench import gameplay
    _, _, trainer, map_id, bit = suite.GYM_SPECS[task['id']]
    progress = blank_evidence()
    progress['map_id'] = map_id
    memory = {W_IS_IN_BATTLE: 2, W_TRAINER_CLASS: trainer}

    class Engine:
        def __init__(self):
            self.memory = memory

        def evidence(self):
            return progress

        def structured(self):
            return {'party': [{'hp': 40}]}

    monkeypatch.setattr(gameplay, 'ui_state', lambda _: {'kind': 'battle_menu'})
    engine = Engine()
    suite.check_start(task, engine)
    progress['map_id'] = 0
    with pytest.raises(ValueError, match='unbeaten'):
        suite.check_start(task, engine)
    progress['map_id'] = map_id
    memory[W_TRAINER_CLASS] = 43
    with pytest.raises(ValueError, match='unbeaten'):
        suite.check_start(task, engine)
    memory[W_TRAINER_CLASS] = trainer
    progress['gym_flags'][bit] = True
    with pytest.raises(ValueError, match='unbeaten'):
        suite.check_start(task, engine)
    progress['gym_flags'][bit] = False
    progress['badges'] = 1 << bit
    with pytest.raises(ValueError, match='unbeaten'):
        suite.check_start(task, engine)


@pytest.mark.parametrize('task', suite.GYM_TASKS, ids=lambda t: t['id'])
def test_gym_success_requires_new_badge_and_defeat_flag(task):
    _, _, _, _, bit = suite.GYM_SPECS[task['id']]
    start = blank_evidence()
    objective = {**task['objective'], 'description': task['name']}
    for badge, flag, expected in [(True, False, False), (False, True, False), (True, True, True)]:
        evaluator = ChallengeEvaluator(start, objective)
        after = deepcopy(start)
        after['badges'] = (1 << bit) if badge else 0
        after['gym_flags'][bit] = flag
        evaluator.observe(after, 1, 0)
        evaluator.observe(after, 2, 0)
        assert evaluator.complete('challenge') is expected


def test_completion_sweep_keeps_original_caps_and_retained_result_provenance():
    from pokeagent_bench.suite_report import summarize
    definition = suite.definition_for('red-skills-completion-v1')
    assert definition['tasks'] == suite.SKILL_TASKS
    assert [(t['id'], t['tokens']) for t in definition['tasks']] == [
        ('item-recovery', 250_000), ('agatha', 750_000), ('lance', 750_000)]
    origin = {'comparison': 'original', 'cell': 'cell-0016', 'benchmark': 'red-v0.37-experimental'}
    report = summarize({'cells': [{'id': 'cell-0001', 'model': 'luna', 'task': 'item-recovery',
                                  'repeat': 1, 'status': 'finished', 'tokens': 100,
                                  'result': {'completed': True}, 'replay': {'verified': True},
                                  'retained_from': origin}],
                        'models': ['luna'], 'phase': 'running', 'budget': 4_750_100,
                        'configuration': {}}, definition)
    assert report['attempts'][0]['retained_from'] == origin
    assert report['tokens'] == 100
    assert not report['ranking_ready']
