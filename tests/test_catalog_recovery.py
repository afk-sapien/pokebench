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


def test_resume_blocks_unknown_charges(tmp_path, monkeypatch):
    make_batch(tmp_path, error={'evaluation_error': 'transport closed', 'usage': {}})
    launch = Mock()
    monkeypatch.setattr(batch, 'run_task', launch)
    with pytest.raises(ValueError, match='Uncertain token usage'):
        batch.run_batch(None, None, None, tmp_path, budget=100000, resume=True)
    launch.assert_not_called()


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


def test_partial_usage_remains_visible_and_blocks_resume(tmp_path):
    make_batch(tmp_path, error={'evaluation_error': 'usage incomplete',
        'usage': {'input_tokens': None, 'output_tokens': 300, 'accounting_complete': False}})
    result = batch.report(tmp_path)
    assert result['cells'][0]['tokens'] == 300
    assert result['models'][0]['accounting_complete'] is False
    with pytest.raises(ValueError, match='Uncertain token usage'):
        batch.run_batch(None, None, None, tmp_path, budget=100000, resume=True)


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
