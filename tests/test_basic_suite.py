from copy import deepcopy
import json
from pathlib import Path

import pytest

from conftest import blank_evidence
from pokeagent_bench.challenges import ChallengeEvaluator, validate_objective
from pokeagent_bench import suite
from pokeagent_bench.suite_report import summarize
from pokeagent_bench.core import write_json
from pokeagent_bench.recovery import pack, unpack


HEAL = {'kind':'heal', 'map_id':41, 'description':'Heal this party in the Center without blacking out'}


def healing_state():
    state = blank_evidence()
    state['challenge'] = {'map_id':1, 'battle':0, 'overworld':True,
                          'party':[{'species':177, 'trainer_id':7, 'dvs':[1,2,3,4,5],
                                    'hp':4, 'max_hp':23, 'status':8}]}
    return state


def recovered(state):
    state = deepcopy(state)
    state['challenge']['map_id'] = 41
    state['challenge']['party'][0].update(hp=23, status=0)
    return state


def test_healing_needs_center_same_party_hp_status_and_control():
    start = healing_state()
    evaluator = ChallengeEvaluator(start, HEAL)
    healed = recovered(start)
    for change in ('wrong-map', 'partial-hp', 'status', 'dialogue'):
        bad = deepcopy(healed)
        if change == 'wrong-map':
            bad['challenge']['map_id'] = 1
        if change == 'partial-hp':
            bad['challenge']['party'][0]['hp'] = 22
        if change == 'status':
            bad['challenge']['party'][0]['status'] = 8
        if change == 'dialogue':
            bad['challenge']['overworld'] = False
        assert not evaluator.observe(bad, 1, 0)
        assert not evaluator.observe(bad, 2, 0)
    assert not evaluator.observe(healed, 3, 0)
    assert evaluator.observe(healed, 4, 0)


@pytest.mark.parametrize('condition', ['blackout', 'replacement'])
def test_healing_cannot_pass_after_blackout_or_party_replacement_even_after_resume(condition):
    start = healing_state()
    evaluator = ChallengeEvaluator(start, HEAL)
    bad = deepcopy(start)
    if condition == 'blackout':
        bad['challenge']['party'][0]['hp'] = 0
    else:
        bad['challenge']['party'][0]['trainer_id'] = 99
    evaluator.observe(bad, 1, 0)
    evaluator = unpack(json.loads(json.dumps(pack(evaluator))))
    healed = recovered(start)
    assert not evaluator.observe(healed, 2, 0)
    assert not evaluator.observe(healed, 3, 0)
    assert not evaluator.complete('challenge')


def test_healing_rejects_full_health_and_invalid_map():
    with pytest.raises(ValueError, match='damaged'):
        ChallengeEvaluator(recovered(healing_state()), HEAL)
    with pytest.raises(ValueError):
        validate_objective(dict(HEAL, map_id=True))


def batch_cells():
    return [{'id':f'cell-{i:04d}', 'model':'model', 'task':t['id'], 'repeat':1,
             'status':'pending', 'token_limit':t['tokens']} for i,t in enumerate(suite.TASKS, 1)]


def finish(cell, success, tokens=10):
    cell.update(status='finished', tokens=tokens, replay={'verified':True},
                result={'completed':success, 'stop_reason':'completed' if success else 'token_budget',
                        'wall_seconds':1})


def test_scores_require_full_coverage_and_include_budget_failures():
    cells = batch_cells()
    batch = {'cells':cells, 'models':['model'], 'phase':'running', 'budget':4000000,'configuration':{}}
    finish(cells[0], True)
    assert summarize(batch)['models'][0]['score'] is None
    for cell in cells[1:]:
        finish(cell, False)
    report = summarize(batch)
    assert report['models'][0]['score'] == 20
    assert report['tokens'] == 50
    cells[1].update(status='error',tokens=30)
    report = summarize(batch)
    assert report['models'][0]['score'] is None
    assert report['tokens'] == 70
    assert report['models'][0]['errors'] == 1


def test_repeat_score_is_average_not_best_of(monkeypatch):
    monkeypatch.setattr(suite, 'validate', lambda *args: {'definition':suite.DEFINITION})
    proposal = suite.plan(Path('.'), ['model'], 2)
    for cell in proposal['cells']:
        finish(cell, cell['repeat']==1)
    batch = dict(proposal, phase='finished',budget=8000000,configuration={})
    assert summarize(batch)['models'][0]['score'] == 50
    assert proposal['maximum_tokens'] == 7_500_000


def mock_runtime(tmp_path, monkeypatch):
    root = tmp_path/'suite'
    root.mkdir()
    write_json(root/'suite.json', {'test':True})
    rom = tmp_path/'rom'
    rom.write_bytes(b'rom')
    monkeypatch.setattr(suite, 'validate', lambda *args, **kwargs: {'definition':suite.DEFINITION,
        'fixtures': {t['id']: {'scenario': 'fixtures/'+t['id']} for t in suite.TASKS}})
    monkeypatch.setattr('pokeagent_bench.gameplay.load_catalog', lambda *args: {'definition':suite.DEFINITION})
    return root, rom


def test_batch_reserves_full_task_budget_before_any_model_call(tmp_path, monkeypatch):
    root, rom = mock_runtime(tmp_path, monkeypatch)
    monkeypatch.setattr('pokeagent_bench.cli.execute', lambda *args: pytest.fail('Must not call model'))
    batch = suite.run_batch(root, rom, tmp_path, tmp_path/'batch', ['model'], budget=1)
    assert batch['phase'] == 'paused at batch budget'
    assert all(c['status']=='pending' for c in batch['cells'])
    assert not (tmp_path/'batch/cell-0001').exists()


def test_resume_skips_finished_trials_and_never_resets_budget(tmp_path, monkeypatch):
    root, rom = mock_runtime(tmp_path, monkeypatch)
    calls = []
    def execute(args):
        calls.append(args.model)
        return {'state':'finished', 'completed':True, 'stop_reason':'completed',
                'usage':{'input_tokens':100,'output_tokens':10,'accounting_complete':True}}
    monkeypatch.setattr('pokeagent_bench.cli.execute', execute)
    monkeypatch.setattr('pokeagent_bench.session.replay', lambda *a: {'verified':True})
    output=tmp_path/'batch'
    first=suite.run_batch(root,rom,tmp_path,output,['model'],budget=1_000_000)
    assert len(calls)==3
    assert first['phase']=='paused at batch budget'
    resumed=suite.run_batch(root,rom,tmp_path,output,budget=2_000_000,resume=True)
    assert len(calls)==5
    assert resumed['phase']=='finished'
    assert suite.accounted(resumed['cells'])==550


def test_batch_stops_on_provider_error_and_reports_usage(tmp_path, monkeypatch):
    root, rom = mock_runtime(tmp_path, monkeypatch)
    monkeypatch.setattr('pokeagent_bench.cli.execute', lambda *args: {
        'state':'finished','completed':False,'stop_reason':'provider_error',
        'usage':{'input_tokens':25,'output_tokens':4,'accounting_complete':False}})
    batch=suite.run_batch(root,rom,tmp_path,tmp_path/'batch',['model'],budget=4_000_000)
    assert batch['phase']=='stopped for error'
    assert batch['cells'][0]['status']=='error'
    assert suite.accounted(batch['cells'])==29
    assert batch['cells'][1]['status']=='pending'


def test_controller_recipe_preserves_truncated_input(tmp_path):
    write = {'executed_frames':9,'action':{'button':'up','hold_frames':8,'release_frames':16}}
    (tmp_path/'actions.jsonl').write_text(json.dumps(write)+'\n')
    assert list(suite.controller_rows(tmp_path)) == [{'button':'up','hold_frames':8,'release_frames':1}]


def test_reexport_does_not_link_to_another_batches_old_replay(tmp_path, monkeypatch):
    from pokeagent_bench import suite_report
    from pokeagent_bench.core import digest
    fixture=tmp_path/'suite'
    fixture.mkdir()
    (fixture/'suite.json').write_text('{}')
    for task in suite.TASKS:
        path=fixture/'fixtures'/task['id']
        path.mkdir(parents=True)
        write_json(path/'scenario.json', {'objective':{'description':'test'}})
    definition={'definition':suite.DEFINITION,'definition_sha256':'test','fixtures':{t['id']:{'scenario':'fixtures/'+t['id'], 'state_sha256':'abc'} for t in suite.TASKS}}
    monkeypatch.setattr(suite_report,'validate',lambda *a, **kwargs:definition)
    batch_root=tmp_path/'batch'
    batch_root.mkdir()
    cells=batch_cells()
    finish(cells[0],True)
    batch={'models':['model'],'cells':cells,'phase':'running','budget':4000000,
           'configuration':{'suite_sha256':digest((fixture/'suite.json').read_bytes())}}
    write_json(batch_root/'batch.json',batch)
    run=batch_root/cells[0]['id']
    run.mkdir()
    (run/'decisions.jsonl').write_text('test')
    (run/'manifest.json').write_text('first runtime')
    (run/'result.json').write_text('first result')
    targets=[]
    def export(runs, target):
        targets.append(target)
        target.write_text('review')
    monkeypatch.setattr('pokeagent_bench.review.export_review',export)
    out=tmp_path/'report.html'
    suite_report.export_report(fixture,batch_root,out)
    (run/'manifest.json').write_text('second runtime')
    suite_report.export_report(fixture,batch_root,out)
    assert len(targets)==2 and targets[0]!=targets[1]
    assert targets[1].name in out.read_text()
    assert targets[0].name not in out.read_text()


def test_suite_cli_returns_failure_status_for_batch_error(monkeypatch):
    from pokeagent_bench import cli
    monkeypatch.setattr('sys.argv', ['pokeagent','suite','catalog'])
    monkeypatch.setattr(cli,'execute',lambda args:{'phase':'stopped for error'})
    assert cli.main()==1


def test_sweep_gate_preserves_all_planned_cells_and_resumes_without_repeating(tmp_path, monkeypatch):
    root, rom = mock_runtime(tmp_path, monkeypatch)
    calls = []
    def execute(args):
        calls.append(args.model)
        return {'state':'finished', 'completed':True, 'stop_reason':'completed',
                'usage':{'input_tokens':100,'output_tokens':10,'accounting_complete':True}}
    monkeypatch.setattr('pokeagent_bench.cli.execute', execute)
    monkeypatch.setattr('pokeagent_bench.session.replay', lambda *a: {'verified':True})
    output=tmp_path/'batch'
    first=suite.run_batch(root,rom,tmp_path,output,['one','two','three'],repeats=3,
                          budget=33750000,pause_after_cells=15)
    assert len(first['cells'])==45
    assert len(calls)==15
    assert first['phase']=='paused for sweep audit'
    assert all(c['repeat']==1 for c in first['cells'] if c['status']=='finished')
    resumed=suite.run_batch(root,rom,tmp_path,output,budget=33750000,resume=True)
    assert len(calls)==45
    assert resumed['phase']=='finished'
    assert suite.accounted(resumed['cells'])==4950
