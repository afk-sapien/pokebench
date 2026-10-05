from types import SimpleNamespace

import pytest

from pokeagent_bench import release
from pokeagent_bench.core import digest, encoded, write_json


MODELS = [
    {'model': 'gpt-6-astra', 'provider': 'codex', 'effort': 'medium'},
    {'model': 'claude-haiku-4-5-20251001', 'provider': 'claude', 'effort': 'medium'},
]
TASKS = [
    {'id': 'starter', 'tokens': 100, 'score_eligible': True},
    {'id': 'lorelei-tactics', 'tokens': 200, 'score_eligible': True},
]


def register(tmp_path, monkeypatch, *, variants=3, budget=50_000_000):
    from pokeagent_bench import gameplay, recovery
    root = tmp_path / 'release'
    root.mkdir()
    rom = tmp_path / 'rom.gb'
    rom.write_bytes(b'private fixture')
    registration = {'fixtures': {}}
    for task in TASKS:
        registration['fixtures'][task['id']] = []
        for index in range(variants):
            scenario = root / 'fixtures' / task['id'] / str(index)
            scenario.mkdir(parents=True)
            (scenario / 'initial.state').write_bytes(b'state')
            write_json(scenario / 'scenario.json', {})
            registration['fixtures'][task['id']].append({
                'scenario': str(scenario.relative_to(root)),
                'manifest_sha256': digest((scenario / 'scenario.json').read_bytes()),
                'state_sha256': digest(b'state'),
            })
    write_json(root / 'fixture-registration.json', registration)
    protocol = dict(id='test-release', tasks=TASKS, models=MODELS, variants=variants,
        total_token_budget=budget, source_sha256='source', rom_sha256=digest(rom.read_bytes()),
        core={'version': 'frozen'}, transports={'verified': True}, catalog_sha256='catalog', in_flight_reserve=100000,
        fixture_registration_sha256=digest((root / 'fixture-registration.json').read_bytes()))
    protocol['sha256'] = digest(encoded(protocol))
    write_json(root / 'protocol.json', protocol)
    write_json(root / 'batch.json', dict(phase='ready', protocol_sha256=protocol['sha256'],
        cells=release.plan(TASKS, MODELS, variants)))
    monkeypatch.setattr(release, 'transport_details', lambda models, task: {'verified': True})
    monkeypatch.setattr(release, 'source_hash', lambda: 'source')
    monkeypatch.setattr(release, 'core_provenance', lambda: {'version': 'frozen'})
    monkeypatch.setattr(gameplay, 'load_catalog', lambda path: {})
    monkeypatch.setattr(gameplay, 'catalog_hash', lambda data: 'catalog')
    monkeypatch.setattr(recovery, 'lock_run', lambda path: SimpleNamespace(close=lambda: None))
    return root, rom, tmp_path


def outcome(*, completed=False, reason='battle_loss', tokens=40, complete_accounting=True):
    return {'state': 'finished', 'completed': completed, 'stop_reason': reason,
        'usage': {'available': True, 'accounting_complete': complete_accounting,
                  'input_tokens': tokens, 'output_tokens': 0, 'calls': 1}, 'wall_seconds': 1}


def finish(root, batch, index, result=None):
    cell = batch['cells'][index]
    target = root / 'runs' / cell['id']
    target.mkdir(parents=True)
    write_json(target / 'result.json', result or outcome())
    cell.update(status='finished', replay={'verified': True},
                result_sha256=digest((target / 'result.json').read_bytes()))


def test_plan_completes_paired_tasks_before_next_task():
    cells = release.plan(TASKS, MODELS, 3)
    assert [c['task'] for c in cells[:6]] == ['lorelei-tactics'] * 6
    assert [c['variant'] for c in cells[:6]] == [1, 1, 2, 2, 3, 3]
    assert [c['model'] for c in cells[:4]] == [MODELS[0]['model'], MODELS[1]['model'], MODELS[1]['model'], MODELS[0]['model']]
    assert all(c['effective_effort'] is None for c in cells if c['provider'] == 'claude')
    assert all(c['effective_effort'] == 'medium' for c in cells if c['provider'] == 'codex')


@pytest.mark.parametrize('change', [
    lambda cells: cells.reverse(),
    lambda cells: cells[0].update(token_limit=1),
    lambda cells: cells[0].update(model='another-model'),
    lambda cells: cells.pop(),
])
def test_mutable_batch_cannot_change_registered_experiment(tmp_path, monkeypatch, change):
    root, _, _ = register(tmp_path, monkeypatch)
    protocol, batch = release.read(root / 'protocol.json'), release.read(root / 'batch.json')
    change(batch['cells'])
    with pytest.raises(ValueError, match='Batch'):
        release.validate_batch(protocol, batch)


def test_ranking_waits_for_identical_complete_variant_coverage(tmp_path, monkeypatch):
    root, _, _ = register(tmp_path, monkeypatch)
    batch = release.read(root / 'batch.json')
    for index in range(5):
        finish(root, batch, index, outcome(completed=True, reason='completed'))
    write_json(root / 'batch.json', batch)
    summary = release.report(root)
    assert not summary['scored_tasks']
    assert all(row['score'] is None for row in summary['models'])
    finish(root, batch, 5)
    write_json(root / 'batch.json', batch)
    summary = release.report(root)
    assert summary['scored_tasks'] == ['lorelei-tactics']
    scores = {row['model']: row['score'] for row in summary['models']}
    assert scores[MODELS[0]['model']] == 100
    assert scores[MODELS[1]['model']] == pytest.approx(200 / 3)


def test_finished_result_cannot_change_after_audit(tmp_path, monkeypatch):
    root, _, _ = register(tmp_path, monkeypatch)
    batch = release.read(root / 'batch.json')
    finish(root, batch, 0)
    write_json(root / 'batch.json', batch)
    target = root / 'runs' / batch['cells'][0]['id'] / 'result.json'
    write_json(target, outcome(tokens=1))
    with pytest.raises(ValueError, match='changed'):
        release.report(root)


@pytest.mark.parametrize('reason', ['provider_error', 'infrastructure_error', 'usage_unavailable', 'observation_budget', 'interrupted', 'paused'])
def test_framework_errors_are_not_model_failures(reason):
    with pytest.raises(ValueError, match='Infrastructure'):
        release.validate_result(outcome(reason=reason))


def test_runner_checks_replay_before_marking_finished(tmp_path, monkeypatch):
    from pokeagent_bench import cli, session
    root, rom, game_data = register(tmp_path, monkeypatch)
    calls = []
    def execute(args):
        calls.append(args)
        args.output.mkdir(parents=True)
        result = outcome()
        write_json(args.output / 'result.json', result)
        return result
    monkeypatch.setattr(cli, 'execute', execute)
    monkeypatch.setattr(session, 'replay', lambda rom, target: {'verified': False})
    summary = release.run(root, rom, game_data)
    assert len(calls) == 1
    assert summary['finished'] == 0
    assert summary['attempts'][0]['status'] == 'error'
    assert summary['attempts'][0]['error'] == 'ValueError'
    assert (root / 'private-errors' / 'cell-0001.txt').read_text().find('Controller replay did not verify') >= 0
    assert 'Controller replay' not in str(summary)


def test_unknown_provider_usage_stops_sweep_and_marks_lower_bound(tmp_path, monkeypatch):
    from pokeagent_bench import cli
    root, rom, game_data = register(tmp_path, monkeypatch)
    calls = []
    def execute(args):
        calls.append(args)
        args.output.mkdir(parents=True)
        result = outcome(reason='provider_error', complete_accounting=False)
        write_json(args.output / 'result.json', result)
        return result
    monkeypatch.setattr(cli, 'execute', execute)
    summary = release.run(root, rom, game_data)
    assert len(calls) == 1
    assert summary['tokens'] == 40
    assert summary['tokens_are_lower_bound']
    assert not summary['accounting_complete']
    assert not summary['scored_tasks']


def test_total_budget_stops_before_starting_unfunded_attempt(tmp_path, monkeypatch):
    from pokeagent_bench import cli
    root, rom, game_data = register(tmp_path, monkeypatch, budget=100199)
    monkeypatch.setattr(cli, 'execute', lambda args: pytest.fail('Unfunded attempt started'))
    summary = release.run(root, rom, game_data)
    assert summary['status'] == 'paused at total token budget'
    assert summary['tokens'] == 0


def test_release_budget_cannot_exceed_authorized_cap(tmp_path, monkeypatch):
    root, rom, game_data = register(tmp_path, monkeypatch, budget=50_000_001)
    with pytest.raises(ValueError, match='authorization'):
        release.run(root, rom, game_data)


def test_bad_fixture_state_fails_before_provider_call(tmp_path, monkeypatch):
    from pokeagent_bench import cli
    root, rom, game_data = register(tmp_path, monkeypatch)
    registration = release.read(root / 'fixture-registration.json')
    fixture = registration['fixtures']['lorelei-tactics'][0]
    (root / fixture['scenario'] / 'initial.state').write_bytes(b'changed')
    monkeypatch.setattr(cli, 'execute', lambda args: pytest.fail('Changed fixture reached provider'))
    with pytest.raises(ValueError, match='state changed'):
        release.run(root, rom, game_data)


def test_complete_sweep_preserves_all_expected_cells_and_exact_command_policy(tmp_path, monkeypatch):
    from pokeagent_bench import cli, session
    root, rom, game_data = register(tmp_path, monkeypatch, variants=1)
    calls = []
    def execute(args):
        calls.append(args)
        assert args.context_turns == 8
        assert args.compact_at == 12000
        assert args.codex_policy == 'bounded'
        assert args.max_actions_per_decision == 1
        args.output.mkdir(parents=True)
        result = outcome(completed=True, reason='completed')
        write_json(args.output / 'result.json', result)
        return result
    monkeypatch.setattr(cli, 'execute', execute)
    monkeypatch.setattr(session, 'replay', lambda rom, target: {'verified': True})
    summary = release.run(root, rom, game_data)
    assert len(calls) == 4
    assert summary['finished'] == 4
    assert summary['status'] == 'finished'
    assert summary['tokens'] == 160
    assert summary['accounting_complete']
    assert all(row['score'] == 100 for row in summary['models'])


def test_changed_cli_blocks_before_model_execution(tmp_path, monkeypatch):
    from pokeagent_bench import cli
    root, rom, game_data = register(tmp_path, monkeypatch)
    monkeypatch.setattr(release, 'transport_details', lambda models, task: {'upgraded': True})
    monkeypatch.setattr(cli, 'execute', lambda args: pytest.fail('Changed CLI reached provider'))
    with pytest.raises(ValueError, match='CLI version'):
        release.run(root, rom, game_data)
    assert (root / 'private-errors' / 'sweep-preflight.txt').exists()
