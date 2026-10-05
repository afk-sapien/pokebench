from copy import deepcopy

import pytest

from conftest import blank_evidence
from pokeagent_bench.challenges import ChallengeEvaluator, validate_objective

OBJECTIVE = {'kind': 'wild-battle', 'description': 'Win this wild Pokemon battle without fleeing or catching it.'}


def initial_state():
    state = blank_evidence()
    state['challenge'] = {'battle': 1, 'battle_type': 0, 'enemy_species': 165,
                          'party': [{'species': 177, 'hp': 21, 'experience': 202}]}
    return state


def test_wild_win_requires_experience_and_exit_confirmed_twice():
    state = initial_state()
    evaluator = ChallengeEvaluator(state, OBJECTIVE)
    state['challenge']['party'][0]['experience'] += 24
    assert not evaluator.observe(state, 1, 0)
    assert not evaluator.observe(state, 2, 0)
    state['challenge']['battle'] = 0
    assert not evaluator.observe(state, 3, 0)
    assert evaluator.observe(state, 4, 0)
    assert evaluator.score == 1


@pytest.mark.parametrize('failure', ['escape', 'capture', 'loss', 'replacement', 'demo', 'invalid'])
def test_wild_failure_cannot_gain_credit_from_later_encounter(failure):
    state = initial_state()
    evaluator = ChallengeEvaluator(deepcopy(state), OBJECTIVE)
    if failure == 'capture':
        state['challenge']['party'].append({'species': 165, 'hp': 10, 'experience': 10})
    elif failure == 'loss':
        state['challenge']['battle'] = 255
        state['challenge']['party'][0]['hp'] = 0
    elif failure == 'replacement':
        state['challenge']['enemy_species'] = 36
    elif failure == 'demo':
        state['challenge']['battle_type'] = 1
    elif failure == 'invalid':
        state['valid'] = False
    evaluator.observe(state, 1, 0)
    state['challenge']['battle'] = 0
    assert not evaluator.observe(state, 2, 0)
    assert not evaluator.observe(state, 3, 0)
    later = initial_state()
    later['challenge']['party'][0]['experience'] += 50
    evaluator.observe(later, 4, 0)
    later['challenge']['battle'] = 0
    assert not evaluator.observe(later, 5, 0)
    assert not evaluator.observe(later, 6, 0)
    assert evaluator.score == 0


@pytest.mark.parametrize('battle,battle_type', [(0, 0), (2, 0), (255, 0), (1, 1)])
def test_wild_checkpoint_rejects_non_wild_encounters(battle, battle_type):
    state = initial_state()
    state['challenge'].update(battle=battle, battle_type=battle_type)
    with pytest.raises(ValueError, match='live normal wild'):
        ChallengeEvaluator(state, OBJECTIVE)


def test_wild_objective_cannot_embed_private_fields():
    with pytest.raises(ValueError, match='unexpected fields'):
        validate_objective(dict(OBJECTIVE, enemy_species=165))
