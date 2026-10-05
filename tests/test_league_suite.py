from copy import deepcopy
from types import SimpleNamespace

import pytest

from conftest import blank_evidence
from pokeagent_bench import suite
from pokeagent_bench.challenges import ChallengeEvaluator
from pokeagent_bench.cli import parser, execute
from pokeagent_bench.suite_report import summarize, export_report
from pokeagent_bench.core import digest, write_json


def league_start():
    state = blank_evidence()
    state.update(badges=255, gym_flags=[True] * 8, map_id=245)
    return state


def test_champion_requires_victory_registration_and_hall_location():
    initial = league_start()
    objective = dict(suite.LEAGUE_TASK['objective'], description='Become Champion')
    state = deepcopy(initial)
    state['elite'] = {name: True for name in state['elite']}
    for change in ({}, {'champion': True}, {'champion': True, 'map_id': 118},
                   {'champion': True, 'hall_of_fame': 1},
                   {'champion': True, 'hall_of_fame': 1, 'map_id': 118, 'valid': False}):
        evaluator = ChallengeEvaluator(initial, objective)
        wrong = dict(state, **change)
        assert not evaluator.observe(wrong, 1, 0)
        assert not evaluator.observe(wrong, 2, 0)
    evaluator = ChallengeEvaluator(initial, objective)
    state.update(champion=True, hall_of_fame=1, map_id=118)
    assert not evaluator.observe(state, 3, 0)
    assert evaluator.observe(state, 4, 0)
    assert evaluator.score == 1


@pytest.mark.parametrize('condition', ['rematch', 'elite-won', 'champion', 'wrong-map', 'no-badge',
                                       'injured', 'status', 'battle', 'transition', 'valid'])
def test_league_fixture_rejects_earned_progress_and_bad_starts(monkeypatch, condition):
    progress = league_start()
    state = {'party':[{'hp':100, 'max_hp':100, 'status':0}],
             'location':{'map_id':245}, 'battle':{'kind':'none'}}
    ui = {'kind':'overworld'}
    monkeypatch.setattr('pokeagent_bench.gameplay.ui_state', lambda memory: ui)
    if condition == 'rematch':
        progress['hall_of_fame'] = 1
    if condition == 'elite-won':
        progress['elite']['Lorelei'] = True
    if condition == 'champion':
        progress['champion'] = True
    if condition == 'wrong-map':
        state['location']['map_id'] = 120
    if condition == 'no-badge':
        progress['badges'] = 127
    if condition == 'injured':
        state['party'][0]['hp'] = 99
    if condition == 'status':
        state['party'][0]['status'] = 8
    if condition == 'battle':
        state['battle']['kind'] = 'trainer'
    if condition == 'transition':
        ui['kind'] = 'transition'
    engine = SimpleNamespace(structured=lambda:state, evidence=lambda:progress, memory={})
    if condition == 'valid':
        suite.check_start(suite.LEAGUE_TASK, engine)
    else:
        with pytest.raises(ValueError):
            suite.check_start(suite.LEAGUE_TASK, engine)


def test_six_tasks_and_league_only_use_selected_budgets_and_scores(monkeypatch):
    assert len(suite.DEFINITION['tasks']) == 5
    assert execute(parser().parse_args(['suite', 'catalog', '--suite-id', 'red-league-v1'])) == suite.LEAGUE_DEFINITION
    for definition, count, budget in [(suite.LEAGUE_DEFINITION, 1, 3_000_000),
                                       (suite.EXPANDED_DEFINITION, 6, 6_750_000)]:
        monkeypatch.setattr(suite, 'validate', lambda *args: {'definition':definition})
        proposal = suite.plan('.', ['model'], 1)
        assert len(proposal['cells']) == count
        assert proposal['maximum_tokens'] == budget
        for cell in proposal['cells']:
            cell.update(status='finished', tokens=10, replay={'verified':True},
                        result={'completed':cell['task'] == 'league'})
        report = summarize(dict(proposal, phase='finished', budget=budget, configuration={}), definition)
        assert report['suite'] == definition['id']
        assert report['models'][0]['score'] == pytest.approx(100/count)
    with pytest.raises(ValueError, match='Unknown suite'):
        suite.definition_for('invented')


def test_league_report_has_one_task_and_no_basic_score(tmp_path, monkeypatch):
    fixture = tmp_path/'fixtures/league'
    fixture.mkdir(parents=True)
    write_json(fixture/'scenario.json', {'objective':{'description':'Become Champion'}})
    definition = {'definition':suite.LEAGUE_DEFINITION, 'definition_sha256':'test', 'core':{'version':'test'}, 'rom_sha256':'rom',
                  'fixtures':{'league':{'scenario':'fixtures/league', 'state_sha256':'test'}}}
    monkeypatch.setattr('pokeagent_bench.suite_report.validate', lambda *args, **kwargs:definition)
    write_json(tmp_path/'suite.json', definition)
    output = tmp_path/'league.html'
    export_report(tmp_path, None, output)
    assert '1 / 1' in output.read_text()
    assert 'Become Champion' in output.read_text()
    assert 'Get a starter' not in output.read_text()

    report = suite.read(output.with_suffix('.json'))
    assert report['configuration']['suite_sha256'] == digest((tmp_path/'suite.json').read_bytes())
    assert report['models'] == []
    assert report['attempts'] == []
    assert not report['ranking_ready']
