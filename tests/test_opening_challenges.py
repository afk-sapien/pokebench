from copy import deepcopy

import pytest

from conftest import blank_evidence
from pokeagent_bench.challenges import ChallengeEvaluator


def opening_state():
    state = blank_evidence()
    state['map_id'] = 38
    state['challenge'] = {'player_name': 'RED', 'party_count': 1, 'party_species': [177],
                          'owned': [7], 'parcel': 0, 'parcel_delivered': False, 'balls': 5,
                          'battle': 0, 'battle_type': 0, 'enemy_species': 165}
    return state


def test_starter_can_begin_with_empty_party_but_requires_story_and_valid_mon():
    state = opening_state()
    state['valid'] = False
    state['challenge'].update(party_count=0, party_species=[], owned=[])
    evaluator = ChallengeEvaluator(state, {'kind': 'opening', 'target': 'starter', 'description': 'Get a starter'})
    current = deepcopy(state)
    current['valid'] = True
    current['challenge'].update(party_count=1, party_species=[177])
    assert not evaluator.observe(current, 1, 0)
    current['story']['starter'] = True
    assert not evaluator.observe(current, 2, 0)
    assert evaluator.observe(current, 3, 0)
    state['challenge']['player_name'] = ''
    with pytest.raises(ValueError, match='valid game'):
        ChallengeEvaluator(state, evaluator.objective)


def test_parcel_requires_delivery_consumption_and_pokedex():
    state = opening_state()
    state['challenge']['parcel'] = 1
    evaluator = ChallengeEvaluator(state, {'kind': 'opening', 'target': 'parcel', 'description': 'Deliver the parcel'})
    current = deepcopy(state)
    current['challenge']['parcel'] = 0
    assert not evaluator.observe(current, 1, 0)
    current['challenge']['parcel_delivered'] = True
    assert not evaluator.observe(current, 2, 0)
    current['story']['pokedex'] = True
    assert not evaluator.observe(current, 3, 0)
    assert evaluator.observe(current, 4, 0)


def test_capture_requires_new_party_member_during_real_wild_battle():
    state = opening_state()
    state['story']['pokedex'] = True
    objective = {'kind': 'capture', 'description': 'Catch a first wild Pokemon'}
    evaluator = ChallengeEvaluator(state, objective)
    current = deepcopy(state)
    current['challenge'].update(party_count=2, party_species=[177, 165], owned=[7, 19])
    assert not evaluator.observe(current, 1, 0)
    assert not evaluator.observe(current, 2, 0)
    evaluator = ChallengeEvaluator(state, objective)
    battle = deepcopy(state)
    battle['challenge']['battle'] = 1
    evaluator.observe(battle, 1, 0)
    current['challenge']['battle'] = 1
    assert not evaluator.observe(current, 2, 0)
    current['challenge']['battle'] = 0
    assert not evaluator.observe(current, 3, 0)
    assert evaluator.observe(current, 4, 0)


def test_old_man_capture_demonstration_cannot_score():
    state = opening_state()
    state['story']['pokedex'] = True
    state['challenge'].update(battle=1, battle_type=1)
    evaluator = ChallengeEvaluator(state, {'kind': 'capture', 'description': 'Catch a first wild Pokemon'})
    current = deepcopy(state)
    current['challenge'].update(battle=0, party_count=2, party_species=[177, 165], owned=[7, 19])
    assert not evaluator.observe(current, 1, 0)
    assert not evaluator.observe(current, 2, 0)


def test_capture_waits_for_pending_nickname_and_party_data():
    state = opening_state()
    state['story']['pokedex'] = True
    state['challenge']['battle'] = 1
    evaluator = ChallengeEvaluator(state, {'kind': 'capture', 'description': 'Catch a first wild Pokemon'})
    current = deepcopy(state)
    current['valid'] = False
    current['challenge'].update(party_count=2, party_species=[177, 0], owned=[7, 19])
    assert not evaluator.observe(current, 1, 0)
    current['valid'] = True
    current['challenge']['party_species'][1] = 165
    assert not evaluator.observe(current, 2, 0)
    current['challenge']['battle'] = 0
    assert not evaluator.observe(current, 3, 0)
    assert evaluator.observe(current, 4, 0)



def roundtrip_start():
    state = opening_state()
    state['story']['starter'] = True
    return state


def test_roundtrip_requires_collection_then_completed_handover_and_survives_recovery():
    from pokeagent_bench.recovery import pack, unpack
    state = roundtrip_start()
    objective = {'kind': 'opening', 'target': 'parcel-roundtrip', 'description': 'Collect and return the parcel'}
    evaluator = ChallengeEvaluator(state, objective)
    delivered = deepcopy(state)
    delivered['challenge']['parcel_delivered'] = True
    delivered['story']['pokedex'] = True
    assert not evaluator.observe(delivered, 1, 0)
    assert not evaluator.observe(delivered, 2, 0)
    pickup = deepcopy(state)
    pickup['challenge']['parcel'] = 1
    pickup['valid'] = False
    evaluator.observe(pickup, 3, 0)
    assert not evaluator.parcel_collected
    pickup['valid'] = True
    assert not evaluator.observe(pickup, 4, 0)
    assert evaluator.parcel_collected
    evaluator = unpack(pack(evaluator))
    assert evaluator.parcel_collected
    incomplete = deepcopy(delivered)
    incomplete['story']['pokedex'] = False
    assert not evaluator.observe(incomplete, 5, 0)
    incomplete = deepcopy(delivered)
    incomplete['challenge']['parcel'] = 1
    assert not evaluator.observe(incomplete, 6, 0)
    incomplete = deepcopy(delivered)
    incomplete['challenge']['battle'] = 2
    assert not evaluator.observe(incomplete, 7, 0)
    assert not evaluator.observe(delivered, 8, 0)
    assert evaluator.observe(delivered, 9, 0)


@pytest.mark.parametrize('field,value', [
    ('starter', False), ('pokedex', True), ('parcel', 1),
    ('parcel_delivered', True), ('party_species', [165]), ('party_count', 2),
])
def test_roundtrip_rejects_incompatible_starts(field, value):
    state = roundtrip_start()
    section = 'story' if field in ('starter', 'pokedex') else 'challenge'
    state[section][field] = value
    with pytest.raises(ValueError, match='roundtrip requires'):
        ChallengeEvaluator(state, {'kind': 'opening', 'target': 'parcel-roundtrip', 'description': 'Collect and return'})
