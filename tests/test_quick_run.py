import json

import pytest

from pokeagent_bench import catalog_batch, catalog_execution, quick_run
from pokeagent_bench.cli import main, parser
from pokeagent_bench.core import write_json

# No model is called here. The task runner is replaced by one that writes a finished result.
SMOKE = quick_run.SUITES['smoke'][2]


@pytest.fixture
def data(tmp_path, monkeypatch):
    """A setup folder whose inventory lists the smoke tasks, one held task and the campaign."""
    root = tmp_path / 'data'
    (root / 'game-data').mkdir(parents=True)
    (root / 'game-data' / 'current.json').write_text('{}')
    rom = tmp_path / 'red.gb'
    rom.write_bytes(b'rom')
    (root / 'setup.json').write_text(json.dumps({'rom': str(rom)}))
    rows = []
    for task, runnable in [(name, True) for name in SMOKE] + [('battle-prepared-gym', False), ('campaign-full-game', True)]:
        folder = root / 'fixtures' / task
        folder.mkdir(parents=True)
        write_json(folder / 'scenario.json', {'state_sha256': 'state-' + task, 'catalog_sha256': 'spec-' + task})
        rows.append({'id': task, 'category': task.split('-')[0], 'mode': catalog_batch.task_definition(task)['mode'],
                     'runnable': runnable, 'variants': [{'variant': 'default', 'path': str(folder)}]})
    listing = {'tasks': rows, 'runnable': sum(row['runnable'] for row in rows)}
    for module in (catalog_batch, quick_run):
        monkeypatch.setattr(module, 'inventory', lambda fixtures: listing)
    monkeypatch.setattr(catalog_execution, 'select_scenario', lambda fixtures, task, variant: fixtures / task)
    monkeypatch.chdir(tmp_path)
    return root


@pytest.fixture
def runs(monkeypatch):
    """Record each launched task and write a finished result that used 1,000 tokens."""
    launched = []

    def fake(fixtures, task, rom, game_data, output, **options):
        launched.append((task, options))
        output.mkdir(parents=True)
        usage = {'input_tokens': 900, 'output_tokens': 100, 'calls': 1}
        write_json(output / 'result.json', {'state': 'finished', 'score': 1, 'score_max': 1, 'usage': usage})

    monkeypatch.setattr(catalog_batch, 'run_task', fake)
    return launched


def command(monkeypatch, *words):
    monkeypatch.setattr('sys.argv', ['pokebench', 'run', *words])
    return main()


def test_smoke_runs_three_tasks_and_prints_a_plain_summary(data, runs, monkeypatch, capsys):
    assert command(monkeypatch, '--model', 'claude-sonnet-5-5', '--suite', 'smoke') == 0
    text = capsys.readouterr().out
    assert [task for task, _ in runs] == list(SMOKE)
    assert all(options['provider'] == 'claude' and options['model'] == 'claude-sonnet-5-5' for _, options in runs)
    assert {options['reasoning_effort'] for _, options in runs} == {'low'}
    assert 'Suite smoke (PokeBench), model claude:claude-sonnet-5-5' in text
    assert 'Worst case 4.3M tokens' in text and 'Reference budget 500K.' in text
    assert '[3/3] battle-wild-basics finished score 100, 1K tokens' in text
    assert 'Finished 3 of 3 runs, 0 errors.' in text
    assert 'Tokens used 3K. Reference budget 500K.' in text and 'Warning' not in text
    assert text.count('not a benchmark result') == 2
    plan = json.loads((data.parent / 'runs' / 'smoke-claude-sonnet-5-5' / 'plan.json').read_text())
    assert plan['suite'] == 'smoke' and plan['note'].startswith('Setup check only')


def test_dry_run_prints_the_estimate_and_starts_nothing(data, runs, monkeypatch, capsys):
    assert command(monkeypatch, '--model', 'codex:gpt-6-sol', '--suite', 'short', '--dry-run', '--input-price', '2') == 0
    text = capsys.readouterr().out
    assert 'Runs: 3 over 3 tasks' in text
    assert 'Left out, fixture needs revalidation: battle-prepared-gym' in text
    assert 'Reference budget 60.0M' in text
    assert 'costs about $120.00 and the worst case about $8.70' in text
    assert runs == [] and not (data.parent / 'runs').exists()


def test_reference_budget_only_warns_and_every_task_gets_its_own_caps(data, runs, monkeypatch, capsys):
    # Earlier tasks spend past the budget. Later tasks must still get their full caps, whatever the order.
    words = ('--model', 'gpt-6-sol', '--suite', 'smoke', '--output', 'out')
    assert command(monkeypatch, *words, '--budget', '1000') == 0
    assert [task for task, _ in runs] == list(SMOKE)
    assert [options['token_limit'] for _, options in runs] == [
        catalog_batch.task_definition(task)['token_limit'] for task in SMOKE]
    text = capsys.readouterr().out
    assert 'Finished 3 of 3 runs' in text
    assert 'Tokens used 3K. Reference budget 1K.' in text
    assert 'Warning: this run passed the reference budget. Every task still ran at its own caps.' in text
    report = json.loads((data.parent / 'out' / 'report.json').read_text())
    assert (report['token_budget'], report['tokens_used'], report['worst_case_tokens']) == (1000, 3000, 4_350_000)


def test_the_same_command_resumes_after_a_stop(data, runs, monkeypatch, capsys):
    words = ('--model', 'gpt-6-sol', '--suite', 'smoke', '--output', 'out')
    finish, stops = catalog_batch.run_task, []

    def stop_at_second(fixtures, task, *args, **options):
        if task == SMOKE[1] and not stops:
            stops.append(task)
            raise KeyboardInterrupt
        finish(fixtures, task, *args, **options)

    monkeypatch.setattr(catalog_batch, 'run_task', stop_at_second)
    with pytest.raises(KeyboardInterrupt):
        command(monkeypatch, *words)
    assert len(runs) == 1
    capsys.readouterr()
    assert command(monkeypatch, *words) == 0
    assert [task for task, _ in runs] == list(SMOKE)
    text = capsys.readouterr().out
    assert 'Resuming: 1 of 3 runs already finished, 1K tokens used.' in text
    assert 'Finished 3 of 3 runs' in text


def test_a_failed_task_is_named_and_later_tasks_still_run(data, runs, monkeypatch, capsys):
    words = ('--model', 'gpt-6-sol', '--suite', 'smoke', '--output', 'out')
    finish = catalog_batch.run_task

    def fail_first(fixtures, task, *args, **options):
        if task == SMOKE[0]:
            raise RuntimeError('fixture would not load')
        finish(fixtures, task, *args, **options)

    monkeypatch.setattr(catalog_batch, 'run_task', fail_first)
    assert command(monkeypatch, *words) == 0
    assert [task for task, _ in runs] == list(SMOKE[1:])
    text = capsys.readouterr().out
    assert 'Finished 2 of 3 runs, 1 errors.' in text
    assert f'{SMOKE[0]} failed and is not retried' in text and 'Delete ' in text
    assert 'Some token usage of a failed task is unknown' in text
    assert 'Setup works' not in text and 'Not every run finished' not in text


def test_interrupted_task_continues_from_its_checkpoint(data, runs, monkeypatch, capsys):
    words = ('--model', 'gpt-6-sol', '--suite', 'smoke', '--output', 'out')
    assert command(monkeypatch, *words) == 0
    cell = data.parent / 'out' / 'cell-0002'
    write_json(cell / 'result.json', {'state': 'interrupted', 'usage': {'input_tokens': 900, 'output_tokens': 100}})
    (cell / 'recovery.json').write_text('{}')
    resumed = []

    def fake_resume(args):
        resumed.append(args.run)
        write_json(args.run / 'result.json', {'state': 'finished', 'score': 1, 'score_max': 1,
                                              'usage': {'input_tokens': 1800, 'output_tokens': 200}})

    monkeypatch.setattr('pokeagent_bench.cli.execute', fake_resume)
    quick_run.run_suite(parser().parse_args(['run', *words]))
    assert [path.resolve() for path in resumed] == [cell]
    assert 'Finished 3 of 3 runs' in capsys.readouterr().out


def test_long_suite_uses_the_published_decision_limit_and_effort(data, runs, monkeypatch, capsys):
    assert command(monkeypatch, '--model', 'claude:claude-fable-5-2', '--suite', 'long') == 0
    assert [(task, options['decision_limit'], options['reasoning_effort']) for task, options in runs] == [
        ('campaign-full-game', 2000, 'medium')]
    # The published Long runs used these, not the single-run defaults of 20K actions and 6 h.
    assert runs[0][1]['run_limits'] == {'max_actions': 150_000, 'max_frames': 10_000_000,
                                        'max_wall_seconds': 86_400, 'max_loop_tokens': 2_000_000,
                                        'max_milestone_tokens': 10_000_000}
    text = capsys.readouterr().out
    assert 'Campaign: 1 of 1 points' in text and '150K controller actions' in text


def test_smoke_cells_keep_the_single_run_limits(data, runs, monkeypatch):
    assert command(monkeypatch, '--model', 'claude-sonnet-5-5', '--suite', 'smoke') == 0
    assert all(options['run_limits'] is None for _, options in runs)


def test_catalog_run_passes_run_limits_to_the_session(tmp_path, monkeypatch):
    import pokeagent_bench.cli as cli
    monkeypatch.setattr(catalog_execution, 'select_scenario', lambda *args: tmp_path)
    captured = []
    monkeypatch.setattr(cli, 'execute', lambda args: captured.append(args))
    catalog_execution.run_task(tmp_path, 'campaign-full-game', 'rom', 'game', tmp_path / 'out',
                               provider='claude', model='test', decision_limit=2000,
                               run_limits=quick_run.LONG_LIMITS)
    args = captured[0]
    assert (args.max_actions, args.max_frames, args.max_wall_seconds, args.max_loop_tokens,
            args.max_milestone_tokens) == (150_000, 10_000_000, 86_400, 2_000_000, 10_000_000)
    with pytest.raises(ValueError, match='Run limits'):
        catalog_execution.run_task(tmp_path, 'campaign-full-game', 'rom', 'game', tmp_path / 'out',
                                   provider='claude', model='test', run_limits={'max_note_bytes': 1})


def test_the_random_player_runs_smoke_for_free_and_nothing_else(data, runs, monkeypatch, capsys):
    assert command(monkeypatch, '--provider', 'random', '--suite', 'smoke') == 0
    text = capsys.readouterr().out
    assert [task for task, _ in runs] == list(SMOKE)
    assert all(options['provider'] == 'random' and options['model'] == 'random' for _, options in runs)
    assert 'model random:random' in text and 'The random player calls no model and uses no tokens.' in text
    assert 'leaderboard models used' not in text
    assert (data.parent / 'runs' / 'smoke-random' / 'plan.json').is_file()
    for words in (('--provider', 'random', '--suite', 'short'), ('--provider', 'random', '--suite', 'long'),
                  ('--model', 'random:x', '--suite', 'long')):
        assert command(monkeypatch, *words) != 0
        assert 'The random player runs the smoke suite only' in capsys.readouterr().err
    assert command(monkeypatch, '--suite', 'smoke') != 0
    assert 'run --suite smoke --provider random' in capsys.readouterr().err
    assert len(runs) == 3


def test_clear_errors_for_the_common_mistakes(data, runs, monkeypatch, capsys, tmp_path):
    assert command(monkeypatch, '--model', 'llama-3', '--suite', 'smoke') != 0
    assert 'need --provider codex, claude or openai-compatible' in capsys.readouterr().err
    assert command(monkeypatch, '--model', 'gpt-6-sol', '--suite', 'smoke', '--data', 'nowhere') != 0
    assert 'pokebench setup --rom' in capsys.readouterr().err
    assert command(monkeypatch, '--model', 'gpt-6-sol', '--suite', 'smoke', '--output', 'out') == 0
    assert command(monkeypatch, '--model', 'gpt-6-luna', '--suite', 'smoke', '--output', 'out') != 0
    assert 'holds a different run' in capsys.readouterr().err
    assert command(monkeypatch, '--model', 'gpt-6-sol') != 0
    assert 'Use --suite, or supply --rom, --scenario, --output, --provider' in capsys.readouterr().err
