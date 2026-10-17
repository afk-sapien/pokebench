"""Runner integration, permissions and restart behavior for registered tasks."""
from copy import deepcopy
import json

import pytest

from pokeagent_bench.catalog_execution import inventory
from pokeagent_bench.challenges import PreparationEvaluator, create_challenge_evaluator
from pokeagent_bench.core import digest, encoded
from pokeagent_bench.evaluation_catalog import task_definition, validate_run_spec
from pokeagent_bench.recovery import pack, unpack
from pokeagent_bench.session import Session


def task_scenario(task_id):
    task = task_definition(task_id)
    kind = 'preparation-submission' if task['mode'] == 'preparation' else 'catalog-task'
    return {'task_id': task_id, 'tested_skill': task['tested_skill'], 'action_policy': task['action_policy'],
            'rom_sha256': 'test', 'objective': {'kind': kind, 'task_id': task_id, 'description': task['agent_goal']}}


def navigation_facts(map_id=1):
    return {'valid': True, 'map_id': map_id, 'battle': 0, 'overworld': True, 'party': [], 'items': [],
            'ui': {'kind': 'overworld', 'selected_text': None}}


def test_session_uses_catalog_grader_and_persists_completion(tmp_path, engine, monkeypatch):
    import pokeagent_bench.catalog_runtime as runtime
    monkeypatch.setattr(runtime, 'catalog_evidence', lambda game, task: navigation_facts(41 if game.frame else 1))
    session = Session(engine, tmp_path / 'run', task_scenario('navigation-town-landmark'), goal='challenge')
    try:
        observation = session.act('walk', 'up', 8, 24)
        assert session.frame == 2
        assert observation['status']['completed']
        assert session.evaluator.score == 1
        result = json.loads((session.output / 'result.json').read_text())
        assert result['task_id'] == 'navigation-town-landmark'
        assert result['score'] == result['score_max'] == 1
        assert 'catalog' not in observation
    finally:
        session.close()


def test_new_evaluator_can_resume_one_confirmation_without_losing_history():
    objective = task_scenario('navigation-town-landmark')['objective']
    evaluator = create_challenge_evaluator({'catalog': navigation_facts()}, objective)
    assert evaluator.observe(navigation_facts(41), 1, 0) == []
    restored = unpack(json.loads(json.dumps(pack(evaluator))))
    assert restored.observe(navigation_facts(41), 2, 0)
    assert restored.complete()
    assert restored.visits == {41}


def test_preparation_session_never_awards_a_game_completion(tmp_path, engine):
    session = Session(engine, tmp_path / 'prep', task_scenario('preparation-lead-selection'), goal='challenge')
    try:
        assert isinstance(session.evaluator, PreparationEvaluator)
        session.act('wait', None, 2, 0)
        assert not session.reason
        assert not session.evaluator.complete()
        restored = unpack(json.loads(json.dumps(pack(session.evaluator))))
        assert not restored.complete()
        session.finish('submitted')
        result = json.loads((session.output / 'result.json').read_text())
        assert result['outcome_category'] == 'submitted'
        assert result['completed'] is False
    finally:
        session.close()


def test_catalog_manual_policy_cannot_be_overridden(tmp_path, engine):
    with pytest.raises(ValueError, match='cannot be overridden'):
        Session(engine, tmp_path / 'bad', task_scenario('operations-heal-potion-target'),
                goal='challenge', action_policy='assisted-gameplay-v1')
    with pytest.raises(ValueError, match='registered goal'):
        Session(engine, tmp_path / 'bad-goal', task_scenario('navigation-town-landmark'), goal='first-gym')


def test_changed_task_definition_cannot_be_used_for_replay():
    task = task_definition('navigation-town-landmark')
    manifest = {'scenario': {'task_id': task['id']}, 'evaluation_spec_sha256': digest(encoded(task))}
    validate_run_spec(manifest)
    altered = deepcopy(manifest)
    altered['evaluation_spec_sha256'] = '0' * 64
    with pytest.raises(ValueError, match='specification changed'):
        validate_run_spec(altered)


def test_inventory_needs_real_matching_state_and_spec(tmp_path):
    task = task_definition('navigation-forest-crossing')
    root = tmp_path / task['id']
    root.mkdir()
    state = b'private-state'
    manifest = {**task_scenario(task['id']), 'catalog_sha256': digest(encoded(task)), 'state_sha256': digest(state)}
    (root / 'scenario.json').write_text(json.dumps(manifest))
    (root / 'initial.state').write_bytes(state)
    (root / 'start-validation.json').write_text(json.dumps({'passed': True}))
    rows = inventory(tmp_path)['tasks']
    assert next(row for row in rows if row['id'] == task['id'])['runnable']
    assert sum(row['runnable'] for row in rows) == 1
    (root / 'initial.state').write_bytes(b'changed')
    assert not next(row for row in inventory(tmp_path)['tasks'] if row['id'] == task['id'])['runnable']


def test_batch_average_weights_tasks_not_variant_count(tmp_path):
    from pokeagent_bench.catalog_batch import report
    cells = []
    outcomes = [('battle', 'a', 1), ('battle', 'a', 1), ('battle', 'b', 0), ('campaign', 'c', 0.5)]
    for index, (category, task, value) in enumerate(outcomes):
        key = f'cell-{index}'
        cells.append({'id': key, 'category': category, 'task_id': task, 'mode': 'gameplay',
                      'provider': 'codex', 'model': 'test'})
        directory = tmp_path / key
        directory.mkdir()
        (directory / 'result.json').write_text(json.dumps({'state': 'finished', 'score': value,
            'score_max': 1, 'usage': {'input_tokens': 10, 'output_tokens': 1}}))
    cells.append({'id': 'pending', 'category': 'battle', 'task_id': 'd', 'mode': 'gameplay',
                  'provider': 'codex', 'model': 'test'})
    (tmp_path / 'plan.json').write_text(json.dumps({'protocol': 'test', 'cells': cells}))
    models = report(tmp_path)['models']
    assert len(models) == 2
    summary = next(row for row in models if row['benchmark'] == 'pokebench')
    campaign = next(row for row in models if row['benchmark'] == 'pokebench-long')
    assert campaign['available_category_average'] is None
    assert campaign['campaign_mean_progress'] == .5
    assert summary['category_scores'] == {'battle': 0.5}
    assert summary['available_category_average'] == 0.5
    assert summary['completed'] == 3
    assert summary['planned'] == 4
    assert summary['tokens'] == 33


def test_new_raw_fixture_input_policy_queues_releases_without_advancing(engine):
    from pokeagent_bench.core import BUTTONS
    from pokeagent_bench.session import initialize_controls
    before = engine.save()
    initialize_controls(engine, {})
    assert engine.inputs == []
    initialize_controls(engine, {'input_policy': 'release-all-before-first-tick-v1'})
    assert engine.inputs == [('release', button, 0) for button in BUTTONS]
    assert engine.save() == before
    assert engine.frame == 0
    with pytest.raises(ValueError, match='Unknown fixture input policy'):
        initialize_controls(engine, {'input_policy': 'unknown'})


def test_inventory_variants_share_one_task_weight(tmp_path):
    from pokeagent_bench.catalog_batch import report
    from pokeagent_bench.core import write_json
    cells = []
    for index, (task, group, value) in enumerate([
            ('checklist', 'checklist', 1), ('bag-space', 'checklist', 0), ('healing', 'healing', 1)]):
        cell = {'id': f'cell-{index}', 'task_id': task, 'score_group': group,
                'category': 'operations', 'mode': 'gameplay', 'provider': 'codex', 'model': 'test'}
        cells.append(cell)
        path = tmp_path / cell['id']
        path.mkdir()
        write_json(path / 'result.json', {'state': 'finished', 'score': value, 'score_max': 1,
                                         'usage': {'input_tokens': 0, 'output_tokens': 0}})
    write_json(tmp_path / 'plan.json', {'protocol': 'test', 'cells': cells})
    assert report(tmp_path)['models'][0]['category_scores'] == {'operations': .75}


@pytest.mark.parametrize('override,expected', [(None, 40), (7, 7)])
def test_catalog_run_enforces_decision_allowance(tmp_path, monkeypatch, override, expected):
    import pokeagent_bench.catalog_execution as execution
    import pokeagent_bench.cli as cli
    monkeypatch.setattr(execution, 'select_scenario', lambda *args: tmp_path)
    captured = []
    monkeypatch.setattr(cli, 'execute', lambda args: captured.append(args))
    execution.run_task(tmp_path, 'operations-heal-potion-target', 'rom', 'game', tmp_path / 'out',
                       provider='codex', model='test', decision_limit=override)
    assert captured[0].max_model_calls == expected
    assert captured[0].max_total_tokens == 1200000


@pytest.mark.parametrize('limit', [0, -1, True, 1.5])
def test_catalog_rejects_invalid_decision_allowance(tmp_path, monkeypatch, limit):
    import pokeagent_bench.catalog_execution as execution
    monkeypatch.setattr(execution, 'select_scenario', lambda *args: tmp_path)
    with pytest.raises(ValueError, match='Decision limit'):
        execution.run_task(tmp_path, 'operations-heal-potion-target', 'rom', 'game', tmp_path / 'out',
                           provider='codex', model='test', decision_limit=limit)


def test_preparation_cannot_purchase_extra_submissions(tmp_path, monkeypatch):
    import pokeagent_bench.catalog_execution as execution
    monkeypatch.setattr(execution, 'select_scenario', lambda *args: tmp_path)
    with pytest.raises(ValueError, match='one frozen submission'):
        execution.run_task(tmp_path, 'preparation-lead-selection', 'rom', 'game', tmp_path / 'out',
                           provider='codex', model='test', decision_limit=2)


def test_active_focused_tasks_have_explicit_decision_budgets():
    from pokeagent_bench.evaluation_catalog import load_catalog
    for group in load_catalog():
        if group['category'] == 'campaign':
            continue
        for task in group['evals']:
            assert type(task['decision_limit']) is int and task['decision_limit'] > 0
            if group['category'] == 'preparation':
                assert task['decision_limit'] == 1
            else:
                if calibration := task.get('budget_calibration'):
                    assert calibration['reference_verified']
                    assert task['decision_limit'] >= 2 * calibration['reference_controller_inputs']
                    assert task['token_limit'] >= task['decision_limit'] * 15000
                else:
                    assert task['token_limit'] == task['decision_limit'] * 30000
