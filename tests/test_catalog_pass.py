from pathlib import Path

from pokeagent_bench.catalog_pass import choose_cell, ledger, run_pass
from pokeagent_bench.core import write_json


def cells():
    return [
        {'id': 'a', 'task_id': 'battle-a', 'variant': 'default', 'provider': 'codex', 'model': 'sol',
         'decision_limit': 40, 'token_limit': 1200000, 'category': 'battle', 'mode': 'gameplay'},
        {'id': 'b', 'task_id': 'battle-a', 'variant': 'default', 'provider': 'claude', 'model': 'opus',
         'decision_limit': 40, 'token_limit': 1200000, 'category': 'battle', 'mode': 'gameplay'},
        {'id': 'c', 'task_id': 'battle-b', 'variant': 'default', 'provider': 'claude', 'model': 'opus',
         'decision_limit': 60, 'token_limit': 1800000, 'category': 'battle', 'mode': 'gameplay'},
    ]


def outcome():
    return {'state': 'finished', 'score': 0, 'score_max': 1, 'stop_reason': 'model_call_budget',
            'usage': {'input_tokens': 100, 'output_tokens': 10, 'calls': 40, 'accounting_complete': True}}


def test_first_model_failure_unlocks_others_but_interface_errors_do_not():
    group = cells()[:2]
    states = {'a': 'running', 'b': 'pending'}
    assert choose_cell(group, states, {'a'}, {}, 2, 1) is None
    states['a'] = 'finished'
    assert choose_cell(group, states, set(), {'a': outcome()}, 2, 1)['id'] == 'b'
    states['a'] = 'evaluation_error'
    assert choose_cell(group, states, set(), {'a': outcome()}, 2, 1) is None


def test_unchecked_tasks_have_priority_and_provider_concurrency_is_bounded():
    group = cells()
    states = {'a': 'finished', 'b': 'pending', 'c': 'pending'}
    assert choose_cell(group, states, set(), {'a': outcome()}, 2, 1)['id'] == 'c'
    states['c'] = 'running'
    assert choose_cell(group, states, {'c'}, {'a': outcome()}, 2, 1) is None


def test_accounting_reserves_running_cap_without_double_counting():
    group = cells()[:2]
    spent, reserved, unknown = ledger(group, {'a': 'finished', 'b': 'running'}, {'b'},
                                       {'a': outcome(), 'b': outcome()})
    assert spent == 110
    assert reserved == 1264000
    assert unknown == []
    bad = outcome()
    bad['usage']['accounting_complete'] = False
    assert ledger(group, {'a': 'evaluation_error', 'b': 'pending'}, set(), {'a': bad})[2] == ['a']


def test_pass_records_completion_and_uses_frozen_runtime(tmp_path, monkeypatch):
    import pokeagent_bench.catalog_pass as module
    monkeypatch.setattr(module, 'plan', lambda *args: {'cells': cells()[:2], 'protocol': 'test'})
    monkeypatch.setattr(module.time, 'sleep', lambda value: None)
    launched = []
    class Process:
        returncode = 0
        def __init__(self, command, **kwargs):
            destination = Path(command[command.index('--output') + 1])
            destination.mkdir()
            write_json(destination / 'result.json', outcome())
            launched.append((command, kwargs['env']))
        def poll(self):
            return 0
    monkeypatch.setattr(module.subprocess, 'Popen', Process)
    result = run_pass(tmp_path, 'rom', 'game', tmp_path / 'pass', tmp_path / 'web', ['codex:sol'],
                      budget=5000000, workers=2)
    assert result['status'] == 'complete'
    assert result['tokens_used'] == 220
    assert len(launched) == 2
    assert all(command[command.index('--decision-limit') + 1] == '40' for command, env in launched)
    assert all(env['PYTHONPATH'] == str(tmp_path / 'pass' / 'runtime') for command, env in launched)
    assert (tmp_path / 'web' / 'focused-pass-v056.html').exists()
    resumed = run_pass(tmp_path, 'rom', 'game', tmp_path / 'pass', tmp_path / 'web', ['codex:sol'],
                       budget=5000000, workers=2, resume=True)
    assert resumed['tokens_used'] == 220
    assert len(launched) == 2


def test_pass_does_not_shrink_task_budget_to_fill_shared_ceiling(tmp_path, monkeypatch):
    import pokeagent_bench.catalog_pass as module
    monkeypatch.setattr(module, 'plan', lambda *args: {'cells': cells()[:2], 'protocol': 'test'})
    def unexpected(*args, **kwargs):
        raise AssertionError('No paid call is allowed')
    monkeypatch.setattr(module.subprocess, 'Popen', unexpected)
    result = run_pass(tmp_path, 'rom', 'game', tmp_path / 'pass', tmp_path / 'web', ['codex:sol'], budget=100)
    assert result['status'] == 'shared token backstop reached'
    assert all(row['state'] == 'pending' for row in result['cells'])



def test_budget_amendment_only_reduces_recorded_ceiling(tmp_path):
    import pytest
    from pokeagent_bench.catalog_pass import effective_budget
    assert effective_budget(tmp_path, {'token_budget': 200}) == 200
    write_json(tmp_path / 'budget-ceiling.json', {'total_token_budget': 50})
    assert effective_budget(tmp_path, {'token_budget': 200}) == 50
    for invalid in (201, 0, True):
        write_json(tmp_path / 'budget-ceiling.json', {'total_token_budget': invalid})
        with pytest.raises(ValueError, match='only reduce'):
            effective_budget(tmp_path, {'token_budget': 200})


def test_missing_usage_is_reserved_without_relabelling_it_reported(tmp_path):
    import pytest
    from pokeagent_bench.catalog_pass import budget_adjustments
    raw = outcome()
    raw['usage']['accounting_complete'] = False
    assert budget_adjustments(tmp_path, cells(), {'a': raw}, ['a']) == (0, 0, ['a'])
    record = {'archived_reported_tokens': 500, 'unreported_usage_reserves': {
        'a': {'total_upper_bound': 1264000, 'reported_tokens': 110, 'evidence': 'CLI thread ended without final usage'}}}
    write_json(tmp_path / 'budget-adjustments.json', record)
    assert budget_adjustments(tmp_path, cells(), {'a': raw}, ['a', 'b']) == (500, 1263890, ['b'])
    assert raw['usage']['accounting_complete'] is False
    record['unreported_usage_reserves']['a']['total_upper_bound'] = 1
    write_json(tmp_path / 'budget-adjustments.json', record)
    with pytest.raises(ValueError, match='full attempt'):
        budget_adjustments(tmp_path, cells(), {'a': raw}, ['a'])


def test_archived_missing_usage_stays_reserved_when_error_is_retried(tmp_path):
    from pokeagent_bench.catalog_pass import budget_adjustments
    write_json(tmp_path / 'budget-adjustments.json', {
        'archived_reported_tokens': 500, 'archived_unreported_usage_reserve': 1000})
    assert budget_adjustments(tmp_path, cells(), {}, []) == (500, 1000, [])


def test_explicit_dispatch_priority_preserves_pilot_and_provider_limits():
    group = cells()
    group[1]['dispatch_priority'] = -1
    states = {'a': 'finished', 'b': 'pending', 'c': 'pending'}
    assert choose_cell(group, states, set(), {'a': outcome()}, 2, 1)['id'] == 'b'
    states['a'] = 'pending'
    assert choose_cell(group, states, set(), {}, 2, 1)['id'] != 'b'
    states.update(a='finished', c='running')
    assert choose_cell(group, states, {'c'}, {'a': outcome()}, 2, 1) is None


def test_worker_that_finishes_between_poll_and_read_is_not_an_error(tmp_path, monkeypatch):
    import pokeagent_bench.catalog_pass as module
    monkeypatch.setattr(module, 'plan', lambda *args: {'cells': cells()[:1], 'protocol': 'test'})
    monkeypatch.setattr(module.time, 'sleep', lambda value: None)
    class Process:
        returncode = 0
        def __init__(self, command, **kwargs):
            self.destination = Path(command[command.index('--output') + 1])
            self.destination.mkdir()
            write_json(self.destination / 'result.json', {**outcome(), 'state': 'running'})
            self.polls = 0
        def poll(self):
            # The final result lands as the process exits, between any two coordinator calls.
            self.polls += 1
            if self.polls < 2:
                return None
            write_json(self.destination / 'result.json', outcome())
            return 0
    monkeypatch.setattr(module.subprocess, 'Popen', Process)
    result = run_pass(tmp_path, 'rom', 'game', tmp_path / 'pass', tmp_path / 'web', ['codex:sol'],
                      budget=5000000, workers=1)
    assert result['status'] == 'complete'
    assert not (tmp_path / 'pass' / 'a' / 'error.json').exists()


def test_coordinator_failure_stops_workers_and_records_stop(tmp_path, monkeypatch):
    import json
    import signal
    import pytest
    import pokeagent_bench.catalog_pass as module
    monkeypatch.setattr(module, 'plan', lambda *args: {'cells': cells()[:1], 'protocol': 'test'})
    launched = []
    class Process:
        returncode = None
        def __init__(self, command, **kwargs):
            destination = Path(command[command.index('--output') + 1])
            destination.mkdir()
            write_json(destination / 'result.json', {**outcome(), 'state': 'running'})
            self.signals, self.log = [], kwargs['stdout']
            assert kwargs['start_new_session']
            launched.append(self)
        def poll(self):
            return self.returncode
        def send_signal(self, value):
            self.signals.append(value)
        def wait(self, timeout=None):
            self.returncode = 130
            return self.returncode
    monkeypatch.setattr(module.subprocess, 'Popen', Process)
    def broken(*args):
        raise RuntimeError('export failed')
    monkeypatch.setattr(module, 'export_progress', broken)
    with pytest.raises(RuntimeError, match='export failed'):
        run_pass(tmp_path, 'rom', 'game', tmp_path / 'pass', tmp_path / 'web', ['codex:sol'],
                 budget=5000000, workers=1)
    assert launched[0].signals == [signal.SIGINT]
    assert launched[0].log.closed
    stopped = json.loads((tmp_path / 'pass' / 'stopped.json').read_text())
    assert stopped['status'] == 'coordinator error: RuntimeError'
    assert stopped['stopped_workers'] == ['a']
