from copy import deepcopy

import pytest

from conftest import blank_evidence
from pokeagent_bench.challenges import ChallengeEvaluator, validate_objective
from pokeagent_bench.recovery import pack, unpack
from pokeagent_bench import suite


def objective(key):
    task = next(t for t in suite.ADVENTURE_TASKS if t['id'] == key)
    return {**task['objective'], 'description': task['name']}


def evidence():
    result = blank_evidence()
    result['challenge'] = {'map_id': 1, 'battle': 0, 'overworld': True, 'surviving': True,
                           'money': 3000, 'items': {'4': 0, '41': 0, '42': 0}}
    return result


def confirmed(evaluator, state):
    evaluator.observe(state, 1, 0)
    evaluator.observe(state, 2, 0)
    return evaluator.complete('challenge')


def test_navigation_requires_destination_control_and_survival():
    start = evidence()
    for changes in [{'map_id': 1}, {'map_id': 2, 'battle': 1}, {'map_id': 2, 'overworld': False},
                    {'map_id': 2, 'surviving': False}]:
        evaluator = ChallengeEvaluator(start, objective('viridian-forest'))
        after = deepcopy(start)
        after['challenge'].update(changes)
        assert not confirmed(evaluator, after)
    evaluator = ChallengeEvaluator(start, objective('viridian-forest'))
    after = deepcopy(start)
    after['challenge']['map_id'] = 2
    assert not evaluator.observe(after, 1, 0)
    assert evaluator.observe(after, 2, 0)
    with pytest.raises(ValueError, match='already reached'):
        ChallengeEvaluator(after, objective('viridian-forest'))


@pytest.mark.parametrize('key', ['viridian-forest', 'buy-pokeballs', 'fossil'])
def test_blackout_permanently_disqualifies_even_after_resume(key):
    start = evidence()
    evaluator = ChallengeEvaluator(start, objective(key))
    bad = deepcopy(start)
    bad['challenge'].update(battle=255, surviving=False)
    evaluator.observe(bad, 1, 0)
    evaluator = unpack(pack(evaluator))
    recovered = deepcopy(start)
    recovered['challenge'].update(map_id=2 if key=='viridian-forest' else 42, money=1000)
    recovered['challenge']['items'].update({'4': 10, '41': 1})
    assert not confirmed(evaluator, recovered)


def test_shopping_requires_item_gain_payment_correct_shop_and_closed_menus():
    start = evidence()
    good = deepcopy(start)
    good['challenge'].update(map_id=42, money=1000)
    good['challenge']['items']['4'] = 10
    assert confirmed(ChallengeEvaluator(start, objective('buy-pokeballs')), good)
    for key, value in [('money',3000), ('map_id',1), ('overworld',False), ('battle',1)]:
        bad = deepcopy(good)
        bad['challenge'][key] = value
        assert not confirmed(ChallengeEvaluator(start, objective('buy-pokeballs')), bad)
    short = deepcopy(good)
    short['challenge']['items']['4'] = 9
    assert not confirmed(ChallengeEvaluator(start, objective('buy-pokeballs')), short)
    expensive_start = deepcopy(start)
    expensive_start['challenge']['money'] = 1999
    with pytest.raises(ValueError, match='cannot afford'):
        ChallengeEvaluator(expensive_start, objective('buy-pokeballs'))


@pytest.mark.parametrize('item', ['41', '42'])
def test_either_fossil_is_accepted_but_existing_inventory_is_rejected(item):
    start = evidence()
    after = deepcopy(start)
    after['challenge']['items'][item] = 1
    assert confirmed(ChallengeEvaluator(start, objective('fossil')), after)
    with pytest.raises(ValueError, match='already owns'):
        ChallengeEvaluator(after, objective('fossil'))
    after['challenge']['overworld'] = False
    assert not confirmed(ChallengeEvaluator(start, objective('fossil')), after)


@pytest.mark.parametrize('key,field,value', [('viridian-forest','map_id',True), ('buy-pokeballs','quantity',0),
                                            ('buy-pokeballs','unit_price',-1), ('fossil','item_ids',[]),
                                            ('fossil','item_ids',[41,41]), ('fossil','item_ids',[True])])
def test_invalid_adventure_objectives_are_rejected(key, field, value):
    obj = objective(key)
    obj[field] = value
    with pytest.raises(ValueError):
        validate_objective(obj)


def test_nineteen_task_catalog_keeps_previous_definitions_and_budgets(monkeypatch):
    old = deepcopy(suite.ABILITY_V2_DEFINITION)
    new = suite.definition_for('red-adventure-v1')
    expanded = suite.definition_for('red-ability-v3')
    assert len(new['tasks']) == 5
    assert len({t['id'] for t in expanded['tasks']}) == 19
    assert expanded['tasks'][:14] == old['tasks']
    assert suite.ABILITY_V2_DEFINITION == old
    monkeypatch.setattr(suite, 'validate', lambda *args: {'definition':new})
    proposal = suite.plan('.', ['luna','terra','sol'], 1)
    assert len(proposal['cells']) == 15
    assert proposal['maximum_tokens'] == 12_750_000


@pytest.mark.parametrize('problem', ['duplicate', 'missing', 'changed-budget', 'different-rom'])
def test_combining_requires_exact_unchanged_coverage(tmp_path, monkeypatch, problem):
    first = {'definition': deepcopy(suite.ABILITY_V2_DEFINITION), 'rom_sha256': 'same',
             'fixtures': {t['id']: {} for t in suite.ABILITY_V2_DEFINITION['tasks']}}
    second = {'definition': deepcopy(suite.ADVENTURE_DEFINITION), 'rom_sha256': 'same',
              'fixtures': {t['id']: {} for t in suite.ADVENTURE_TASKS}}
    if problem == 'duplicate':
        second = deepcopy(first)
    elif problem == 'missing':
        second['definition']['tasks'].pop()
    elif problem == 'changed-budget':
        second['definition']['tasks'][0]['tokens'] += 1
    else:
        second['rom_sha256'] = 'different'
    monkeypatch.setattr(suite, 'validate', lambda root: first if str(root).endswith('first') else second)
    output = tmp_path/'output'
    with pytest.raises(ValueError):
        suite.combine([tmp_path/'first', tmp_path/'second'], output, 'red-ability-v3')
    assert not output.exists()
