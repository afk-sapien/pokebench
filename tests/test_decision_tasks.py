from copy import deepcopy

import pytest

from conftest import blank_evidence
from pokeagent_bench.challenges import ChallengeEvaluator, validate_objective


def start():
    state=blank_evidence()
    state['challenge']={'battle':2,'battle_type':0,'map_id':245,'overworld':False,'enemy_species':132,'balls':12,
                        'party':[{'species':111,'hp':50,'max_hp':100,'status':0,'trainer_id':1,'dvs':[8,8]}]}
    return state


def guarded(no_faints=False):
    return {'kind':'guarded-milestones','targets':['elite:lorelei','elite:bruno'],
            'no_faints':no_faints,'description':'Win both fights.'}


def test_two_battles_must_both_be_won():
    state=start()
    evaluator=ChallengeEvaluator(state,guarded())
    state['elite']['Lorelei']=True
    evaluator.observe(state,1,0)
    evaluator.observe(state,2,0)
    assert not evaluator.complete('challenge')
    state['elite']['Bruno']=True
    evaluator.observe(state,3,0)
    evaluator.observe(state,4,0)
    assert evaluator.complete('challenge')


def test_faint_violation_cannot_be_erased_by_revival():
    state=start()
    state['challenge']['party'].append({**state['challenge']['party'][0],'species':147})
    evaluator=ChallengeEvaluator(state,guarded(True))
    state['challenge']['party'][0]['hp']=0
    evaluator.observe(state,1,0)
    state['challenge']['party'][0]['hp']=100
    state['elite'].update(Lorelei=True,Bruno=True)
    evaluator.observe(state,2,0)
    evaluator.observe(state,3,0)
    assert evaluator.battle_disqualified and not evaluator.complete('challenge')


def test_rescue_allows_initial_fainted_reserve_but_never_a_blackout():
    state=start()
    state['challenge']['party'].append({**state['challenge']['party'][0],'hp':0,'species':147})
    with pytest.raises(ValueError,match='every Pokemon alive'):
        ChallengeEvaluator(state,guarded(True))
    evaluator=ChallengeEvaluator(state,guarded())
    state['challenge']['battle']=255
    evaluator.observe(state,1,0)
    state['challenge']['battle']=0
    state['elite'].update(Lorelei=True,Bruno=True)
    evaluator.observe(state,2,0)
    assert evaluator.battle_disqualified


@pytest.mark.parametrize('caught',[True,False])
def test_capture_requires_this_encounter_and_survives_ui_transition(caught):
    state=start()
    state['challenge']['battle']=1
    evaluator=ChallengeEvaluator(state,{'kind':'encounter-capture','description':'Catch this Snorlax.'})
    if caught:
        state['challenge']['party'].append({**state['challenge']['party'][0],'species':132})
        evaluator.observe(state,1,0)
    state['challenge'].update(battle=0,enemy_species=0)
    evaluator.observe(state,2,0)
    evaluator.observe(state,3,0)
    assert evaluator.complete('challenge') is caught
    if not caught:
        state['challenge']['battle']=1
        state['challenge']['party'].append({**state['challenge']['party'][0],'species':132})
        evaluator.observe(state,4,0)
        state['challenge']['battle']=0
        evaluator.observe(state,5,0)
        assert not evaluator.complete('challenge')


def test_route_cannot_complete_after_blackout():
    state=start()
    state['challenge'].update(battle=0,map_id=1,overworld=True)
    objective={'kind':'resource-route','map_id':51,'description':'Reach the forest without blacking out.'}
    evaluator=ChallengeEvaluator(state,objective)
    state['challenge']['party'][0]['hp']=0
    evaluator.observe(state,1,0)
    state['challenge']['party'][0]['hp']=100
    state['challenge']['map_id']=51
    evaluator.observe(state,2,0)
    evaluator.observe(state,3,0)
    assert not evaluator.complete('challenge')


def test_no_faint_rule_and_targets_are_explicit_and_validated():
    for changes in ({'targets':[]},{'targets':['elite:lorelei','elite:lorelei']},{'no_faints':'yes'},{'targets':['not-real']}):
        with pytest.raises(ValueError):
            validate_objective({**guarded(),**changes})
    value=guarded()
    before=deepcopy(value)
    assert validate_objective(value)==before and value==before


def test_six_tasks_have_matched_starts_and_separate_pilot_registration():
    from pokeagent_bench.suite import definition_for
    from pokeagent_bench.portal import category
    full=definition_for('red-decisions-v1')
    pilot=definition_for('red-decisions-pilot-v1')
    assert len(full['tasks'])==6
    assert all(t['variants']==5 for t in full['tasks'])
    assert all(t['variants']==1 for t in pilot['tasks'])
    assert len(definition_for('red-ability-v7')['tasks'])==33
    assert full['status']==pilot['status']=='experimental'
    assert all(category(t)!='Other' for t in full['tasks'])
