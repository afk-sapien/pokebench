from copy import deepcopy

import pytest

from conftest import FakeEngine, blank_evidence
from pokeagent_bench.challenges import ChallengeEvaluator
from pokeagent_bench.session import Session
from pokeagent_bench import suite

OBJECTIVE = {'kind': 'battle-milestone', 'target': 'elite:lorelei', 'description': 'Win this battle'}


def initial():
    state = blank_evidence()
    state['challenge'] = {'battle': 2, 'surviving': True}
    return state


def test_wipe_is_permanent_even_if_agent_returns_and_wins():
    state = initial()
    evaluator = ChallengeEvaluator(state, OBJECTIVE)
    state['challenge']['surviving'] = False
    evaluator.observe(state, 1, 0)
    state['challenge'] = {'battle': 0, 'surviving': True}
    state['elite']['Lorelei'] = True
    for frame in range(2, 5):
        assert not evaluator.observe(state, frame, 0)
    assert not evaluator.complete('challenge')


def test_live_win_and_invalid_start():
    state = initial()
    evaluator = ChallengeEvaluator(state, OBJECTIVE)
    state['elite']['Lorelei'] = True
    state['challenge']['battle'] = 0
    evaluator.observe(state, 1, 0)
    evaluator.observe(state, 2, 0)
    assert evaluator.complete('challenge')
    with pytest.raises(ValueError, match='live trainer battle'):
        ChallengeEvaluator(state, OBJECTIVE)


def test_session_stops_at_wipe_frame(tmp_path):
    engine = FakeEngine()
    engine.challenge_evidence = lambda objective: {'battle': 255 if engine.frame else 2, 'surviving': True}
    session = Session(engine, tmp_path/'run', {'objective': OBJECTIVE}, goal='challenge')
    try:
        session.wait('wait', 100)
        assert session.reason == 'battle_loss'
        assert session.frame == 1
    finally:
        session.close()


def test_all_models_get_same_variants_without_best_of_selection(monkeypatch):
    monkeypatch.setattr(suite, 'validate', lambda root: {'definition': deepcopy(suite.TACTICAL_DEFINITION)})
    with pytest.raises(ValueError, match='complete cycles'):
        suite.plan('unused', ['a', 'b'], 1)
    result = suite.plan('unused', ['a', 'b'], 5)
    for model in ('a', 'b'):
        assert [c['variant'] for c in result['cells'] if c['model']==model] == [1, 2, 3, 4, 5]
    assert result['maximum_tokens'] == 5_000_000


def test_cost_and_ability_coverage_require_matching_variants():
    from pokeagent_bench.combined_analysis import summarize
    rows = [dict(task='tactics', model=model, repeat=1, variant=variant,
                 status='finished', replay_verified=True, completed=True)
            for model, variant in [('a', 1), ('b', 2)]]
    eligible, scores = summarize([{'id': 'tactics'}], rows, ['a', 'b'])
    assert eligible == []
    assert all(row['score'] is None for row in scores)


def test_new_catalog_preserves_all_existing_tasks():
    assert suite.ABILITY_V5_DEFINITION['tasks'][:-1] == suite.ABILITY_V4_DEFINITION['tasks']
    assert len(suite.ABILITY_V5_DEFINITION['tasks']) == 27


def test_tactical_team_versions_remain_distinct(monkeypatch):
    from pokeagent_bench import tactical
    import pytest
    monkeypatch.setattr(tactical, 'read_bag', lambda memory: [(82, 1)])
    def party(team):
        return [{'species':species,'level':level,'moves':moves,'hp':100,'max_hp':100,'status':0}
                for species,level,moves in team]
    monkeypatch.setattr(tactical, 'read_party', lambda memory: party(tactical.TEAM_V2))
    tactical.validate_team(None, 2)
    with pytest.raises(ValueError):
        tactical.validate_team(None, 1)
    monkeypatch.setattr(tactical, 'read_party', lambda memory: party(tactical.TEAM))
    tactical.validate_team(None, 1)
    with pytest.raises(ValueError):
        tactical.validate_team(None, 2)
    with pytest.raises(ValueError):
        tactical.validate_team(None, 3)
    assert suite.TACTICAL_V2_TASK['team_version']==2
    assert 'team_version' not in suite.TACTICAL_TASK
