"""Regression coverage for interrupted batches and charged preparation failures."""
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from pokeagent_bench import catalog_batch as batch
from pokeagent_bench import preparation_runtime as prep
from pokeagent_bench.core import write_json


def make_batch(tmp_path, mode='preparation', state=None, error=None, usage_record=None):
    cell = {'id': 'cell-0001', 'category': 'preparation' if mode == 'preparation' else 'navigation',
            'task_id': 'test-task', 'mode': mode, 'provider': 'codex', 'model': 'test'}
    write_json(tmp_path / 'plan.json', {'protocol': 'catalog-batch-v1', 'cells': [cell]})
    run = tmp_path / cell['id']
    run.mkdir()
    if state is not None:
        name = 'preparation-result.json' if mode == 'preparation' else 'result.json'
        write_json(run / name, state)
    if error is not None:
        write_json(run / 'error.json', error)
    if usage_record is not None:
        write_json(run / 'model-usage.json', usage_record)
    return run


def test_preparation_exception_is_excluded_from_model_scores(tmp_path):
    make_batch(tmp_path, state={'submitted': False, 'reason': 'preparation_error',
        'error': 'transport failed', 'usage': {'input_tokens': 0, 'output_tokens': 0}},
        error={'evaluation_error': 'transport failed', 'usage': {}})
    result = batch.report(tmp_path)
    assert result['cells'][0]['state'] == 'evaluation_error'
    assert result['cells'][0]['value'] is None
    assert result['models'][0]['completed'] == 0
    assert result['models'][0]['evaluation_errors'] == 1
    assert result['models'][0]['category_scores'] == {}
    assert result['models'][0]['accounting_complete'] is False


def test_error_overlay_keeps_known_charges(tmp_path):
    usage = {'input_tokens': 12000, 'output_tokens': 300, 'accounting_complete': True}
    make_batch(tmp_path, state={'submitted': False, 'reason': 'preparation_error', 'usage': usage},
               error={'evaluation_error': 'disk error', 'usage': {}}, usage_record=usage)
    result = batch.report(tmp_path)
    assert result['cells'][0]['tokens'] == 12300
    assert result['cells'][0]['state'] == 'evaluation_error'
    assert result['models'][0]['accounting_complete'] is True


@pytest.mark.parametrize('state', ['running', 'paused', 'interrupted'])
def test_resume_surfaces_unfinished_gameplay_before_new_calls(tmp_path, monkeypatch, state):
    make_batch(tmp_path, mode='gameplay', state={'state': state, 'score': 0, 'score_max': 1,
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


def test_resume_surfaces_interrupted_preparation_assessment(tmp_path):
    run = make_batch(tmp_path)
    (run / 'preparation').mkdir()
    write_json(run / 'preparation/result.json', {'state': 'finished', 'stop_reason': 'submitted',
        'usage': {'input_tokens': 200, 'output_tokens': 10}})
    assert batch.report(tmp_path)['cells'][0]['state'] == 'assessment_pending'
    with pytest.raises(ValueError, match='needs recovery'):
        batch.run_batch(None, None, None, tmp_path, budget=100000, resume=True)


def test_resume_blocks_unknown_charges(tmp_path, monkeypatch):
    make_batch(tmp_path, error={'evaluation_error': 'transport closed', 'usage': {}})
    launch = Mock()
    monkeypatch.setattr(batch, 'run_task', launch)
    with pytest.raises(ValueError, match='Uncertain token usage'):
        batch.run_batch(None, None, None, tmp_path, budget=100000, resume=True)
    launch.assert_not_called()


def test_resume_keeps_completed_results_and_known_charges(tmp_path, monkeypatch):
    make_batch(tmp_path, state={'submitted': True, 'assessment': {'win_rate': .6},
        'usage': {'input_tokens': 12000, 'output_tokens': 300}})
    launch = Mock()
    monkeypatch.setattr(batch, 'run_task', launch)
    result = batch.run_batch(None, None, None, tmp_path, budget=100000, resume=True)
    launch.assert_not_called()
    assert result['tokens_used'] == 12300
    assert result['models'][0]['completed'] == 1
    assert result['cells'][0]['value'] == .6


class FakeProvider:
    server = None
    thread_id = None
    provider = 'codex'
    model = 'test'
    reasoning_effort = 'low'

    def __init__(self, failure=None):
        self.failure = failure
        self.closed = False

    def _start(self, deadline):
        self.thread_id = 'fake'

    def _complete(self, *args):
        if self.failure:
            raise self.failure
        return 'malformed output', {'input_tokens': 12000, 'output_tokens': 300}

    def close(self):
        self.closed = True


@pytest.mark.parametrize('failure', ['response', 'transport', 'action'])
def test_preparation_persists_usage_and_error_classification(tmp_path, monkeypatch, failure):
    transport_error = failure == 'transport'
    session = SimpleNamespace(usage={}, output=tmp_path / 'preparation', finish=Mock(), close=Mock())
    monkeypatch.setattr(prep, 'load_engine', lambda *args: (object(), {}))
    monkeypatch.setattr(prep, 'load_catalog', lambda *args: {})
    monkeypatch.setattr(prep, 'Session', lambda *args, **kwargs: session)
    actions = SimpleNamespace(act=Mock(), submit=Mock())
    monkeypatch.setattr(prep, 'PreparationSession', lambda *args: actions)
    monkeypatch.setattr(prep, 'public_preparation_state', lambda *args: {'party': [], 'bag': []})
    provider = FakeProvider(RuntimeError('transport failed') if transport_error else None)
    if failure == 'action':
        action = {key: None for key in ('first', 'second', 'item', 'slot', 'quantity', 'forget')}
        action.update(operation='reorder_party', first=0, second=99)
        provider._complete = Mock(return_value=(json.dumps({'actions': [action]}),
            {'input_tokens': 12000, 'output_tokens': 300}))
        actions.act.side_effect = prep.InvalidPreparationAction('Invalid party slot')
    kwargs = dict(rom=tmp_path, scenario=tmp_path, output=tmp_path, game_data=tmp_path,
                  task_id='preparation-lead-selection', provider=provider)
    if transport_error:
        with pytest.raises(RuntimeError, match='transport failed'):
            prep.run_preparation(**kwargs)
    else:
        prep.run_preparation(**kwargs)
    result = json.loads((tmp_path / 'preparation-result.json').read_text())
    journal = json.loads((tmp_path / 'model-usage.json').read_text())
    assert result['usage'] == journal
    assert journal['accounting_complete'] is (not transport_error)
    if transport_error:
        assert result['evaluation_error'] == 'transport failed'
    else:
        assert result['reason'] == 'invalid_submission'
        assert journal['input_tokens'] + journal['output_tokens'] == 12300
    if failure == 'action':
        actions.act.assert_called_once()
        assert 'evaluation_error' not in result
    else:
        actions.act.assert_not_called()
    actions.submit.assert_not_called()
    assert provider.closed


def test_partial_usage_remains_visible_and_blocks_resume(tmp_path):
    make_batch(tmp_path, error={'evaluation_error': 'usage incomplete',
        'usage': {'input_tokens': None, 'output_tokens': 300, 'accounting_complete': False}})
    result = batch.report(tmp_path)
    assert result['cells'][0]['tokens'] == 300
    assert result['models'][0]['accounting_complete'] is False
    with pytest.raises(ValueError, match='Uncertain token usage'):
        batch.run_batch(None, None, None, tmp_path, budget=100000, resume=True)



def test_offline_reassessment_preserves_original_and_usage(tmp_path):
    from pokeagent_bench.catalog_batch import cell_result
    from pokeagent_bench.core import write_json
    original = {'submitted': True, 'submission_sha256': 'same-submission',
                'usage': {'input_tokens': 200, 'output_tokens': 20, 'accounting_complete': True},
                'assessment': {'evaluation_errors': 1, 'win_rate': None}}
    write_json(tmp_path / 'preparation-result.json', original)
    updated = {'submission_sha256': 'same-submission', 'evaluation_errors': 0,
               'model_calls': 0, 'win_rate': .6}
    write_json(tmp_path / 'reassessment.json', {'assessment': updated, 'reason': 'Controller repair'})
    actual = cell_result(tmp_path)
    assert actual['assessment']['win_rate'] == .6
    assert actual['usage'] == original['usage']
    assert json.loads((tmp_path / 'preparation-result.json').read_text()) == original
    updated['submission_sha256'] = 'different-submission'
    write_json(tmp_path / 'reassessment.json', {'assessment': updated})
    with pytest.raises(ValueError, match='original frozen submission'):
        cell_result(tmp_path)
