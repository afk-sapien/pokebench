"""Regression coverage for interrupted batches, charged failures and stored preparation cells."""
import json
from unittest.mock import Mock

import pytest

from pokeagent_bench import catalog_batch as batch
from pokeagent_bench.core import write_json


def make_batch(tmp_path, state=None, error=None, category='navigation'):
    cell = {'id': 'cell-0001', 'category': category, 'task_id': 'test-task', 'mode': 'gameplay',
            'provider': 'codex', 'model': 'test', 'token_limit': 100000}
    write_json(tmp_path / 'plan.json', {'protocol': 'catalog-batch-v1', 'cells': [cell]})
    run = tmp_path / cell['id']
    run.mkdir()
    if state is not None:
        write_json(run / 'result.json', state)
    if error is not None:
        write_json(run / 'error.json', error)
    return run


def test_task_exception_is_excluded_from_model_scores(tmp_path):
    make_batch(tmp_path, state={'state': 'running', 'score': 0, 'score_max': 1,
        'usage': {'input_tokens': 0, 'output_tokens': 0}},
        error={'evaluation_error': 'transport failed', 'usage': {}})
    result = batch.report(tmp_path)
    assert result['cells'][0]['state'] == 'evaluation_error'
    assert result['cells'][0]['value'] is None
    assert result['models'][0]['completed'] == 0
    assert result['models'][0]['evaluation_errors'] == 1
    assert result['models'][0]['category_scores'] == {}


def test_error_overlay_keeps_known_charges(tmp_path):
    usage = {'input_tokens': 12000, 'output_tokens': 300, 'accounting_complete': True}
    make_batch(tmp_path, state={'state': 'running', 'score': 0, 'score_max': 1, 'usage': usage},
               error={'evaluation_error': 'disk error', 'usage': {}})
    result = batch.report(tmp_path)
    assert result['cells'][0]['tokens'] == 12300
    assert result['cells'][0]['state'] == 'evaluation_error'
    assert result['models'][0]['accounting_complete'] is True


@pytest.mark.parametrize('state', ['running', 'paused', 'interrupted'])
def test_resume_surfaces_unfinished_gameplay_before_new_calls(tmp_path, monkeypatch, state):
    make_batch(tmp_path, state={'state': state, 'score': 0, 'score_max': 1,
        'usage': {'input_tokens': 123, 'output_tokens': 4}})
    plan = json.loads((tmp_path / 'plan.json').read_text())
    plan['cells'].insert(0, {**plan['cells'][0], 'id': 'new-cell'})
    write_json(tmp_path / 'plan.json', plan)
    launch = Mock()
    monkeypatch.setattr(batch, 'run_task', launch)
    with pytest.raises(ValueError, match='needs recovery'):
        batch.run_batch(None, None, None, tmp_path, budget=100000, resume=True)
    launch.assert_not_called()
    assert json.loads((tmp_path / 'report.json').read_text())['cells'][1]['state'] == state


def test_failed_cell_with_unknown_charges_is_reported_and_never_retried(tmp_path, monkeypatch):
    make_batch(tmp_path, error={'evaluation_error': 'transport closed', 'usage': {}})
    launch = Mock()
    monkeypatch.setattr(batch, 'run_task', launch)
    result = batch.run_batch(None, None, None, tmp_path, budget=100000, resume=True)
    launch.assert_not_called()
    assert result['cells'][0]['state'] == 'evaluation_error'
    assert result['models'][0]['accounting_complete'] is False


def test_finished_cell_with_unknown_charges_blocks_resume(tmp_path, monkeypatch):
    make_batch(tmp_path, state={'state': 'finished', 'score': 1, 'score_max': 1,
        'usage': {'input_tokens': 10, 'output_tokens': 1, 'accounting_complete': False}})
    launch = Mock()
    monkeypatch.setattr(batch, 'run_task', launch)
    with pytest.raises(ValueError, match='Uncertain token usage'):
        batch.run_batch(None, None, None, tmp_path, budget=100000, resume=True)
    launch.assert_not_called()


def three_cell_batch(tmp_path, monkeypatch, outcomes):
    """Plan three fresh cells and run them with a launcher that follows the given outcomes in order."""
    cells = [{'id': f'cell-000{i}', 'category': 'navigation', 'task_id': f'task-{i}', 'mode': 'gameplay',
              'provider': 'codex', 'model': 'test', 'token_limit': 100000, 'variant': 'default',
              'fixture_sha256': 'state', 'evaluation_spec_sha256': 'spec'} for i in (1, 2, 3)]
    write_json(tmp_path / 'plan.json', {'protocol': 'catalog-batch-v3-decisions', 'cells': cells})
    monkeypatch.setattr('pokeagent_bench.catalog_execution.select_scenario', lambda *args: tmp_path / 'fixture')
    (tmp_path / 'fixture').mkdir()
    write_json(tmp_path / 'fixture' / 'scenario.json', {'state_sha256': 'state', 'catalog_sha256': 'spec'})
    launched = []

    def launch(fixtures, task, rom, game_data, output, **options):
        outcome = outcomes[len(launched)]
        launched.append(task)
        if outcome == 'fail':
            raise RuntimeError(f'{task} broke')
        output.mkdir(parents=True)
        write_json(output / 'result.json', {'state': outcome, 'score': 1, 'score_max': 1,
                                            'usage': {'input_tokens': 90, 'output_tokens': 10}})

    monkeypatch.setattr(batch, 'run_task', launch)
    return launched


def test_one_failed_task_does_not_block_later_tasks(tmp_path, monkeypatch):
    launched = three_cell_batch(tmp_path, monkeypatch, ['fail', 'finished', 'finished'])
    seen = []
    result = batch.run_batch(None, None, None, tmp_path, budget=100000, resume=True, on_cell=seen.append)
    assert launched == ['task-1', 'task-2', 'task-3']
    assert [row['state'] for row in result['cells']] == ['evaluation_error', 'finished', 'finished']
    assert [row['id'] for row in seen] == ['cell-0001', 'cell-0002', 'cell-0003']
    assert 'task-1 broke' in (tmp_path / 'cell-0001' / 'error.json').read_text()
    # A resume skips the failed cell instead of retrying it.
    launched.clear()
    batch.run_batch(None, None, None, tmp_path, budget=100000, resume=True)
    assert launched == []


def test_two_failures_in_a_row_stop_the_batch(tmp_path, monkeypatch):
    launched = three_cell_batch(tmp_path, monkeypatch, ['fail', 'fail', 'finished'])
    with pytest.raises(RuntimeError, match='task-2 broke'):
        batch.run_batch(None, None, None, tmp_path, budget=100000, resume=True)
    assert launched == ['task-1', 'task-2']
    assert not (tmp_path / 'cell-0003').exists()


def test_provider_pause_still_stops_the_batch(tmp_path, monkeypatch):
    launched = three_cell_batch(tmp_path, monkeypatch, ['fail', 'paused', 'finished'])
    result = batch.run_batch(None, None, None, tmp_path, budget=100000, resume=True)
    assert launched == ['task-1', 'task-2']
    assert [row['state'] for row in result['cells']] == ['evaluation_error', 'paused', 'pending']


def test_resume_keeps_completed_results_and_known_charges(tmp_path, monkeypatch):
    make_batch(tmp_path, state={'state': 'finished', 'score': 3, 'score_max': 5,
        'usage': {'input_tokens': 12000, 'output_tokens': 300}})
    launch = Mock()
    monkeypatch.setattr(batch, 'run_task', launch)
    result = batch.run_batch(None, None, None, tmp_path, budget=100000, resume=True)
    launch.assert_not_called()
    assert result['tokens_used'] == 12300
    assert result['models'][0]['completed'] == 1
    assert result['cells'][0]['value'] == .6


def test_partial_usage_of_a_failed_cell_stays_visible_after_resume(tmp_path):
    make_batch(tmp_path, error={'evaluation_error': 'usage incomplete',
        'usage': {'input_tokens': None, 'output_tokens': 300, 'accounting_complete': False}})
    result = batch.report(tmp_path)
    assert result['cells'][0]['tokens'] == 300
    assert result['models'][0]['accounting_complete'] is False
    resumed = batch.run_batch(None, None, None, tmp_path, budget=100000, resume=True)
    assert resumed['tokens_used'] == 300
    assert resumed['models'][0]['accounting_complete'] is False


def test_stored_preparation_cells_are_kept_on_disk_but_not_read(tmp_path, monkeypatch):
    run = make_batch(tmp_path, state={'state': 'finished', 'score': 1, 'score_max': 1,
        'usage': {'input_tokens': 100, 'output_tokens': 10}})
    old = {'id': 'prep-0001', 'category': 'preparation', 'task_id': 'preparation-lead-selection',
           'mode': 'preparation', 'provider': 'codex', 'model': 'test', 'token_limit': 100000}
    plan = json.loads((tmp_path / 'plan.json').read_text())
    plan['cells'].append(old)
    write_json(tmp_path / 'plan.json', plan)
    # An unfinished stored attempt would block a resume if it were still read.
    (tmp_path / old['id']).mkdir()
    write_json(tmp_path / old['id'] / 'preparation-result.json', {'submitted': True,
        'usage': {'input_tokens': 5000, 'output_tokens': 500}})
    write_json(tmp_path / old['id'] / 'error.json', {'evaluation_error': 'stored', 'usage': {}})
    result = batch.report(tmp_path)
    assert [row['id'] for row in result['cells']] == [run.name]
    assert result['models'][0]['planned'] == 1
    assert result['models'][0]['tokens'] == 110
    assert result['models'][0]['category_scores'] == {'navigation': 1}
    launch = Mock()
    monkeypatch.setattr(batch, 'run_task', launch)
    resumed = batch.run_batch(None, None, None, tmp_path, budget=100000, resume=True)
    launch.assert_not_called()
    assert resumed['worst_case_tokens'] == 100000
    assert (tmp_path / old['id'] / 'preparation-result.json').is_file()
