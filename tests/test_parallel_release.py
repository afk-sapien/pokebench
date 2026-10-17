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


def test_empty_box_reads_do_not_access_emulator_and_nonempty_reads_are_unchanged(monkeypatch):
    from pokesim_core import gen1_ui
    old = gen1_ui.memory_bytes
    monkeypatch.setattr(gen1_ui, 'memory_bytes', old)
    parallel.install_storage_read_fix()
    class Memory:
        def __init__(self):
            self.reads = []
        def __getitem__(self, key):
            self.reads.append(key)
            block = key[1] if isinstance(key, tuple) else key
            assert block.start < block.stop
            return list(range(block.stop - block.start))
    memory = Memory()
    assert gen1_ui.memory_bytes(memory, None, 0xA000, 0) == b''
    assert gen1_ui.memory_bytes(memory, 2, 0xA000, 0) == b''
    assert memory.reads == []
    assert gen1_ui.memory_bytes(memory, None, 0xA000, 3) == b'\x00\x01\x02'
    assert gen1_ui.memory_bytes(memory, 2, 0xA000, 3) == b'\x00\x01\x02'
    assert len(memory.reads) == 2


def test_explicit_budget_amendment_does_not_change_registration(tmp_path):
    protocol = {'sha256': 'a'*64, 'total_token_budget': 50000000}
    assert parallel.execution_budget(tmp_path, protocol) == 50000000
    record = {'protocol_sha256': protocol['sha256'], 'total_token_budget': 300000000}
    record['sha256'] = digest(encoded(record))
    write_json(tmp_path/'budget-authorization.json', record)
    assert parallel.execution_budget(tmp_path, protocol) == 300000000
    assert protocol['total_token_budget'] == 50000000
    record['total_token_budget'] = 400000000
    write_json(tmp_path/'budget-authorization.json', record)
    with pytest.raises(ValueError, match='authorization'):
        parallel.execution_budget(tmp_path, protocol)


def test_reviewed_infrastructure_error_allows_missing_claude_pair_but_not_gameplay_retry():
    failed = {**cell('failed', provider='claude', status='error'), 'model': 'claude', 'budget_hold_tokens': 120}
    pending = {**cell('retry', provider='claude', variant=2), 'model': 'claude'}
    assert parallel.next_cell([failed, pending], 4, 4, 'claude-missing') == pending
    failed['status'] = 'finished'
    assert parallel.next_cell([failed, pending], 4, 4, 'claude-missing') is None


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


def test_exploration_selects_only_missing_claude_pairs_with_smallest_caps():
    cells = [cell('openai'), cell('repeat', provider='claude', variant=2),
             cell('done', provider='claude', status='finished'),
             cell('new', provider='claude', task='two', budget=50),
             cell('costly', provider='claude', task='three', budget=100)]
    for item in cells:
        item['model'] = 'claude' if item['provider'] == 'claude' else 'openai'
    assert parallel.next_cell(cells, 4, 2, 'claude-missing')['id'] == 'new'
    cells[3]['status'] = 'running'
    assert parallel.next_cell(cells, 4, 2, 'claude-missing')['id'] == 'costly'
    cells[4]['status'] = 'running'
    assert parallel.next_cell(cells, 4, 2, 'claude-missing') is None


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


def test_named_trial_never_selects_other_eligible_work():
    first = {**cell('first', provider='claude'), 'model':'claude-a'}
    second = {**cell('second', provider='claude'), 'model':'claude-b'}
    assert parallel.next_cell([first, second], 1, 1, 'claude-missing', 'second') is second
    second['status'] = 'finished'
    assert parallel.next_cell([first, second], 1, 1, 'claude-missing', 'second') is None
    assert parallel.next_cell([first, second], 1, 1, 'claude-missing', 'absent') is None


def test_diagnostic_reservations_are_bound_unique_and_never_refunded(tmp_path):
    protocol = {'sha256':'a'*64}
    assert parallel.diagnostic_holds(tmp_path, protocol) == 0
    record = {'protocol_sha256':protocol['sha256'], 'holds':[{'id':'diagnostic-one', 'token_hold':250000, 'status':'finished'}]}
    record['sha256'] = digest(encoded(record))
    write_json(tmp_path/'diagnostic-reservations.json', record)
    assert parallel.diagnostic_holds(tmp_path, protocol) == 250000
    record['holds'][0]['token_hold'] = 0
    record['sha256'] = digest(encoded({k:v for k,v in record.items() if k != 'sha256'}))
    write_json(tmp_path/'diagnostic-reservations.json', record)
    with pytest.raises(ValueError, match='reservation'):
        parallel.diagnostic_holds(tmp_path, protocol)
    record['holds'] = [{'id':'one', 'token_hold':10}, {'id':'one', 'token_hold':20}]
    record['sha256'] = digest(encoded({k:v for k,v in record.items() if k != 'sha256'}))
    write_json(tmp_path/'diagnostic-reservations.json', record)
    with pytest.raises(ValueError, match='reservation'):
        parallel.diagnostic_holds(tmp_path, protocol)
    with pytest.raises(ValueError, match='checksum'):
        parallel.diagnostic_holds(tmp_path, {'sha256':'b'*64})


def test_frozen_response_adapter_adds_headroom_and_reservation_without_changing_other_settings(monkeypatch):
    from pokeagent_bench import claude_provider
    cls = claude_provider.ClaudeCodeProvider
    monkeypatch.setattr(cls, 'harness', 'claude-code-bounded-gameplay-v1')
    monkeypatch.setattr(cls, 'max_output_tokens', 4096)
    monkeypatch.setattr(cls, 'estimate_next_tokens', lambda self, *args, **kwargs: 20000)
    monkeypatch.setattr(claude_provider, 'subscription_environment', lambda: {'CLAUDE_CODE_MAX_OUTPUT_TOKENS':'4096', 'isolation':'unchanged'})
    parallel.install_response_headroom()
    assert cls.harness == 'claude-code-bounded-gameplay-v2'
    assert cls.max_output_tokens == 8192
    assert cls.estimate_next_tokens(None) == 24096
    assert claude_provider.subscription_environment() == {'CLAUDE_CODE_MAX_OUTPUT_TOKENS':'8192', 'isolation':'unchanged'}
    parallel.install_response_headroom()
    assert cls.estimate_next_tokens(None) == 24096


@pytest.mark.parametrize('remaining,expected', [(900,600), (50,50)])
def test_v3_deadline_never_exceeds_remaining_trial_time_and_reserves_full_response(monkeypatch, remaining, expected):
    from pokeagent_bench import claude_provider
    cls = claude_provider.ClaudeCodeProvider
    monkeypatch.setattr(cls, 'harness', 'claude-code-bounded-gameplay-v1')
    monkeypatch.setattr(cls, 'max_output_tokens', 4096)
    monkeypatch.setattr(cls, '__init__', lambda self: setattr(self, 'config_identity', {}))
    monkeypatch.setattr(cls, 'estimate_next_tokens', lambda self, *args: 20000)
    monkeypatch.setattr(cls, 'decide', lambda self, *args: self._complete('turn', {}, -1))
    monkeypatch.setattr(cls, '_complete', lambda self, method, params, deadline: deadline)
    monkeypatch.setattr(claude_provider, 'subscription_environment', lambda: {'CLAUDE_CODE_MAX_OUTPUT_TOKENS':'4096'})
    monkeypatch.setattr(parallel.time, 'monotonic', lambda: 1000)
    parallel.install_response_budget_v3()
    obj = cls()
    assert obj.decide({}, None, [], None, remaining) == 1000+expected
    assert obj.estimate_next_tokens() == 47904
    assert obj.config_identity == {'max_response_tokens':32000, 'max_decision_seconds':600}
    assert claude_provider.subscription_environment()['CLAUDE_CODE_MAX_OUTPUT_TOKENS'] == '32000'
    parallel.install_response_budget_v3()
    assert obj.estimate_next_tokens() == 47904
