import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from pokeagent_bench import release
from pokeagent_bench.core import digest, encoded, write_json
from test_release import register, outcome

spec = importlib.util.spec_from_file_location('parallel_release', Path(__file__).parents[1] / 'scripts/parallel_release.py')
parallel = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parallel)


def cell(key, provider='codex', status='pending', variant=1, task='one', budget=100):
    return {'id': key, 'provider': provider, 'status': status, 'task': task, 'variant': variant, 'token_limit': budget}


def test_reservations_count_inflight_tokens_once_and_keep_unused_ceiling():
    cells = [cell('done', status='finished'), cell('active', status='running'), cell('new')]
    spent, reserved = parallel.reservation_ledger(cells, {'done': outcome(tokens=40), 'active': outcome(tokens=60)}, 20)
    assert (spent, reserved) == (40, 120)
    assert spent + reserved + 120 > 200
    assert spent + reserved + 120 == 280


def test_worker_overrun_increases_reservation_and_unknown_usage_blocks_admission():
    cells = [cell('active', status='running')]
    assert parallel.reservation_ledger(cells, {'active': outcome(tokens=170)}, 20) == (0, 170)
    with pytest.raises(ValueError, match='incomplete usage'):
        parallel.reservation_ledger(cells, {'active': outcome(complete_accounting=False)}, 20)
    assert parallel.reservation_ledger(cells, {}, 20) == (0, 120)


def test_provider_caps_allow_other_provider_without_crossing_variant_barrier():
    cells = [cell('a', status='running'), cell('b', status='running'), cell('c'),
             cell('d', provider='claude'), cell('e', provider='claude', variant=2)]
    assert parallel.next_cell(cells, 4, 2)['id'] == 'd'
    cells[3]['status'] = 'running'
    assert parallel.next_cell(cells, 4, 2) is None
    cells[0]['status'] = 'finished'
    assert parallel.next_cell(cells, 4, 2)['id'] == 'c'
    assert parallel.next_cell(cells, 2, 2) is None


def setup_coordinator(tmp_path, monkeypatch, budget=50_000_000):
    root, rom, data = register(tmp_path, monkeypatch, variants=1, budget=budget)
    protocol = release.read(root / 'protocol.json')
    models = [{'provider': p, 'model': m, 'effort': 'medium'} for p,m in [
        ('codex', 'gpt-one'), ('codex', 'gpt-two'), ('claude', 'claude-one'), ('claude', 'claude-two')]]
    protocol['models'] = models
    protocol.pop('sha256')
    protocol['sha256'] = digest(encoded(protocol))
    write_json(root / 'protocol.json', protocol)
    write_json(root / 'batch.json', {'phase': 'ready', 'protocol_sha256': protocol['sha256'],
                                   'cells': release.plan(protocol['tasks'], models, 1)})
    monkeypatch.setattr(parallel, 'preflight', lambda *args: (release, protocol, release.read(root / 'batch.json')))
    monkeypatch.setattr(parallel.time, 'sleep', lambda seconds: None)
    return root, rom, data


def test_coordinator_runs_four_trials_and_verifies_all_before_scoring(tmp_path, monkeypatch):
    root, rom, data = setup_coordinator(tmp_path, monkeypatch)
    admitted = []
    peak = []
    def launch(root, rom, game_data, item, resume=False):
        admitted.append(item['id'])
        batch = release.read(root / 'batch.json')
        peak.append(sum(c['status'] == 'running' for c in batch['cells']))
        target = root / 'runs' / item['id']
        target.mkdir(parents=True)
        write_json(target / 'result.json', outcome(completed=True, reason='completed'))
        write_json(root / 'parallel-outcomes' / (item['id'] + '.json'), {
            'status': 'finished', 'replay': {'verified': True}, 'result_sha256': digest((target / 'result.json').read_bytes())})
        return SimpleNamespace(poll=lambda: 0, returncode=0)
    monkeypatch.setattr(parallel, 'launch', launch)
    assert parallel.coordinate(root, rom, data) == 'finished'
    summary = release.read(root / 'release-summary.json')
    assert max(peak) == 4
    assert len(admitted) == len(set(admitted)) == 8
    assert summary['tokens'] == 320
    assert summary['finished'] == 8
    assert all(model['score'] == 100 for model in summary['models'])


def test_parallel_budget_blocks_unfunded_workers(tmp_path, monkeypatch):
    root, rom, data = setup_coordinator(tmp_path, monkeypatch, budget=100199)
    monkeypatch.setattr(parallel, 'launch', lambda *args, **kwargs: pytest.fail('Unfunded trial started'))
    assert parallel.coordinate(root, rom, data) == 'paused at total token budget'


def test_worker_failure_stops_new_admissions_and_preserves_existing_trials(tmp_path, monkeypatch):
    root, rom, data = setup_coordinator(tmp_path, monkeypatch)
    admitted = []
    def launch(root, rom, game_data, item, resume=False):
        admitted.append(item['id'])
        return SimpleNamespace(poll=lambda: 1, returncode=1)
    monkeypatch.setattr(parallel, 'launch', launch)
    status = parallel.coordinate(root, rom, data)
    assert status == 'stopped for incomplete accounting'
    assert len(admitted) == 4
    summary = release.read(root / 'release-summary.json')
    assert summary['finished'] == 0
    assert sum(c['status'] == 'pending' for c in summary['attempts']) == 4
    assert summary['tokens_are_lower_bound']


def test_reviewed_failure_retains_full_allowance_and_remains_outside_score():
    failed = cell('error', status='error')
    failed['budget_hold_tokens'] = 120
    used = outcome(tokens=30, complete_accounting=False)
    assert parallel.reservation_ledger([failed], {'error': used}, 20) == (120, 0)
    pending = cell('next', variant=2)
    assert parallel.next_cell([failed, pending], 4, 2) == pending
    failed['budget_hold_tokens'] = 119
    with pytest.raises(ValueError, match='insufficient'):
        parallel.reservation_ledger([failed], {'error': used}, 20)


def test_reviewed_failure_is_not_retried_and_its_reserve_limits_remaining_work(tmp_path, monkeypatch):
    root, rom, data = setup_coordinator(tmp_path, monkeypatch, budget=100350)
    batch = release.read(root / 'batch.json')
    item = batch['cells'][0]
    item.update(status='error', error='ValueError')
    target = root / 'runs' / item['id']
    target.mkdir(parents=True)
    write_json(target / 'result.json', outcome(reason='provider_error', complete_accounting=False))
    write_json(root / 'batch.json', batch)
    monkeypatch.setattr(parallel, 'launch', lambda *args, **kwargs: pytest.fail('Error hold failed to protect budget'))
    assert parallel.coordinate(root, rom, data, quarantine_cells=[item['id']]) == 'paused at total token budget'
    result = release.read(root / 'batch.json')
    assert result['cells'][0]['status'] == 'error'
    assert result['cells'][0]['budget_hold_tokens'] == 100200
    summary = release.read(root / 'release-summary.json')
    assert not summary['accounting_complete']
    assert summary['finished'] == 0
    assert all(model['score'] is None for model in summary['models'])
