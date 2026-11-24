"""A provider error with no model reply spends nothing. It is retried, then the run pauses and the same command resumes it."""
import json

import pytest

from conftest import FakeEngine
from pokeagent_bench import catalog_batch, catalog_execution, quick_run, recovery, runner
from pokeagent_bench.claude_provider import ClaudeCodeProvider
from pokeagent_bench.cli import main
from pokeagent_bench.core import Limits, digest, write_json
from pokeagent_bench.providers import ProviderError
from pokeagent_bench.recovery import DEFAULT_RESERVE, NO_REPLY, UNCERTAIN, reopen, resume
from pokeagent_bench.runner import run
from pokeagent_bench.session import Session


class Flaky:
    """Answers like a model, except the provider fails with no reply at chosen frames."""
    provider = 'claude-code'
    model = 'claude-sonnet-5-5'
    harness = ClaudeCodeProvider.harness
    config_identity = {}
    prompt = 'test'

    def __init__(self, model=None, *, reasoning_effort='low', failures=None, kind='provider_error', reply=False,
                 extra=None):
        self.reasoning_effort = reasoning_effort
        self.failures = {} if failures is None else failures  # frame -> failures left
        self.kind, self.reply, self.extra = kind, reply, extra or {}
        self.packet_baseline = None
        self.seen = []

    def decide(self, observation, *args):
        self.seen.append(self.packet_baseline)
        if self.failures.get(observation['frame'], 0) > 0:
            self.failures[observation['frame']] -= 1
            raise ProviderError('Claude returned a synthetic provider error',
                                details={'kind': self.kind, 'status': 529, 'no_reply': not self.reply,
                                         'text': 'API Error: 529 Overloaded', **self.extra})
        self.packet_baseline = 'segment'
        return {'actions': [{'button': 'wait', 'hold_frames': 2, 'release_frames': 0}], 'notes': None}, {
            'input_tokens': 10, 'output_tokens': 5}, {}

    def close(self):
        pass


def factory(rom, state):
    engine = FakeEngine()
    engine.frame = int(state.decode().split('-')[-1])
    return engine


@pytest.fixture(autouse=True)
def no_wait(monkeypatch):
    monkeypatch.setattr(runner, 'RETRY_DELAYS', (0, 0, 0))


def start(tmp_path, calls=4):
    rom = tmp_path / 'test.gb'
    rom.write_bytes(b'fake rom')
    session = Session(FakeEngine(), tmp_path / 'run', {'rom_sha256': digest(rom.read_bytes())},
                      limits=Limits(max_model_calls=calls), clock=lambda: 100)
    return session, rom


def read(root, name):
    return [json.loads(line) for line in (root / name).read_text().splitlines()]


def test_a_failed_attempt_is_retried_in_a_fresh_segment(tmp_path):
    session, _ = start(tmp_path)
    provider = Flaky(failures={4: 2})  # decision 3 starts at frame 4
    run(session, provider)
    result = json.loads((session.output / 'result.json').read_text())
    assert result['stop_reason'] == 'model_call_budget'
    assert result['usage']['calls'] == 4 and result['usage']['accounting_complete']
    assert result['usage']['input_tokens'] == 40
    assert [(row['decision'], row['attempt'], row['status']) for row in result['provider_errors']] == [(3, 1, 529), (3, 2, 529)]
    assert {row['text'] for row in result['provider_errors']} == {'API Error: 529 Overloaded'}
    # Each failed attempt drops the segment, so the retry cannot resume a transcript that holds the failed turn.
    assert provider.seen == [None, 'segment', 'segment', None, None, 'segment']
    assert [row['index'] for row in read(session.output, 'decisions.jsonl')] == [1, 2, 3, 4]


def test_exhausted_retries_pause_and_resume_runs_the_same_decision(tmp_path):
    session, rom = start(tmp_path)
    root = session.output
    paused = run(session, Flaky(failures={4: 9}))
    assert paused['state'] == 'paused'
    assert paused['usage']['calls'] == 2 and paused['usage']['accounting_complete']
    assert json.loads((root / 'pending.json').read_text()) == {'decision': 3, 'phase': NO_REPLY}
    assert len(read(root, 'provider-errors.jsonl')) == 4
    restored = resume(rom, root, engine_factory=factory)
    assert restored.resume_metadata['after_provider_error'] == 3
    provider = Flaky()
    final = run(restored, provider)
    assert final['stop_reason'] == 'model_call_budget'
    assert final['actions'] == final['usage']['calls'] == 4
    assert final['usage']['input_tokens'] == 40
    assert provider.seen[0] is None  # the resumed decision starts a fresh segment
    assert [row['index'] for row in read(root, 'decisions.jsonl')] == [1, 2, 3, 4]
    assert [row['operation_id'] for row in read(root, 'actions.jsonl')] == [f'decision-{n}-1' for n in (1, 2, 3, 4)]
    result = json.loads((root / 'result.json').read_text())
    assert [row['attempt'] for row in result['provider_errors']] == [1, 2, 3, 4]
    assert not (root / 'pending.json').exists()


def test_a_subscription_limit_pauses_without_retrying(tmp_path):
    session, rom = start(tmp_path)
    paused = run(session, Flaky(failures={4: 9}, kind='subscription_limit'))
    assert paused['state'] == 'paused'
    assert [row['kind'] for row in read(session.output, 'provider-errors.jsonl')] == ['subscription_limit']
    resume(rom, session.output, engine_factory=factory).close()


class Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


def waiting(monkeypatch, clock, *, stop=False):
    """Replace the wait with one that moves the session clock, and record each wait."""
    waits = []

    def fake(seconds, guard):
        waits.append(seconds)
        clock.now += seconds
        return stop
    monkeypatch.setattr(runner, 'wait', fake)
    monkeypatch.setattr(runner.time, 'time', lambda: 1_000_000.0)
    return waits


def test_a_subscription_limit_waits_for_its_reset_and_asks_again(tmp_path, monkeypatch, capsys):
    session, _ = start(tmp_path)
    session.clock = clock = Clock()
    session.started = clock.now
    waits = waiting(monkeypatch, clock)
    reset = {'resets_at': 1_000_000 + 3 * 3600, 'limit_type': 'five_hour'}
    final = run(session, Flaky(failures={4: 1}, kind='subscription_limit', extra=reset))
    assert waits == [3 * 3600 + runner.RESET_MARGIN]
    assert final['stop_reason'] == 'model_call_budget'
    assert final['usage']['calls'] == 4 and final['usage']['input_tokens'] == 40
    # The wait is not the model's time, so the run's wall clock leaves it out.
    assert final['wall_seconds'] < 60
    assert [row['index'] for row in read(session.output, 'decisions.jsonl')] == [1, 2, 3, 4]
    assert 'Waiting 182 min until' in capsys.readouterr().out


def test_ctrl_c_during_the_reset_wait_pauses_the_run(tmp_path, monkeypatch):
    session, rom = start(tmp_path)
    session.clock = clock = Clock()
    session.started = clock.now
    waiting(monkeypatch, clock, stop=True)
    paused = run(session, Flaky(failures={4: 9}, kind='subscription_limit', extra={'resets_at': 1_000_600}))
    assert paused['state'] == 'paused'
    assert json.loads((session.output / 'pending.json').read_text()) == {'decision': 3, 'phase': NO_REPLY}
    resume(rom, session.output, engine_factory=factory).close()


def test_a_limit_still_hit_after_the_reset_waits_pauses(tmp_path, monkeypatch):
    session, _ = start(tmp_path)
    session.clock = clock = Clock()
    session.started = clock.now
    waits = waiting(monkeypatch, clock)
    paused = run(session, Flaky(failures={4: 9}, kind='subscription_limit', extra={'resets_at': 1_000_600}))
    assert paused['state'] == 'paused'
    assert len(waits) == runner.RESET_WAITS
    assert len(read(session.output, 'provider-errors.jsonl')) == runner.RESET_WAITS + 1


@pytest.mark.parametrize('details, expected', [
    ({'kind': 'subscription_limit', 'resets_at': 1_003_600}, 3600 + runner.RESET_MARGIN),
    ({'kind': 'subscription_limit', 'resets_at': '1970-01-12T14:46:40Z'}, 3600 + runner.RESET_MARGIN),
    ({'kind': 'subscription_limit', 'resets_at': 999_000}, runner.RESET_MARGIN),
    ({'kind': 'subscription_limit', 'resets_at': 1_000_000 + 3 * 86400}, None),
    ({'kind': 'subscription_limit', 'resets_at': None}, None),
    ({'kind': 'subscription_limit', 'resets_at': 'soon'}, None),
    ({'kind': 'subscription_limit'}, None),
    ({'kind': 'provider_error', 'resets_at': 1_003_600}, None),
])
def test_only_a_near_parseable_reset_is_waited_for(details, expected):
    assert runner.until_reset(ProviderError('limit', details=details), now=1_000_000) == expected


def test_an_error_after_a_model_reply_keeps_the_old_refusal(tmp_path):
    session, rom = start(tmp_path)
    stopped = run(session, Flaky(failures={4: 1}, reply=True))
    assert stopped['stop_reason'] == 'provider_error'
    assert stopped['usage']['accounting_complete'] is False
    assert not (session.output / 'provider-errors.jsonl').exists()
    with pytest.raises(ValueError, match='uncertain usage'):
        resume(rom, session.output, engine_factory=factory)


def test_a_weekly_limit_pauses_and_names_its_reset(tmp_path, monkeypatch, capsys):
    session, rom = start(tmp_path)
    session.clock = clock = Clock()
    session.started = clock.now
    waits = waiting(monkeypatch, clock)
    weekly = {'resets_at': 1_000_000 + 3 * 86400, 'limit_type': 'secondary'}
    paused = run(session, Flaky(failures={4: 9}, kind='subscription_limit', extra=weekly))
    # A reset days away is not waited for. The run pauses at once with nothing spent on the decision.
    assert paused['state'] == 'paused' and waits == []
    assert paused['usage']['calls'] == 2 and paused['usage']['accounting_complete']
    assert ('at decision 3. It resets at 1970-01-15 13:46 UTC. The run pauses with its checkpoint kept'
            in capsys.readouterr().out)
    final = run(resume(rom, session.output, engine_factory=factory), Flaky())
    assert final['stop_reason'] == 'model_call_budget' and final['usage']['calls'] == 4


def test_a_provider_error_after_a_reply_reruns_its_decision_with_a_token_reserve(tmp_path):
    session, rom = start(tmp_path)
    root = session.output
    provider = Flaky(failures={4: 1}, reply=True)
    provider.next_decision_token_estimate = 8000
    assert run(session, provider)['stop_reason'] == 'provider_error'
    assert json.loads((root / 'error.json').read_text())['token_reserve'] == 8000
    attempt = reopen(rom, root)
    assert attempt == root.resolve() / 'provider-error-01'
    assert sorted(path.name for path in attempt.iterdir()) == ['error.json', 'final.state', 'pending.json', 'result.json']
    assert json.loads((root / 'pending.json').read_text()) == {
        'decision': 3, 'phase': UNCERTAIN, 'set_aside': 'provider-error-01', 'token_reserve': 8000}
    assert reopen(rom, root) == attempt  # a repeat moves nothing and adds no second record
    [row] = read(root, 'provider-errors.jsonl')
    assert (row['decision'], row['usage'], row['token_reserve'], row['set_aside']) == (3, 'unknown', 8000, 'provider-error-01')
    restored = resume(rom, root, engine_factory=factory)
    # The run stops 8000 tokens early, and the manifest keeps the task's own cap for verify.
    assert restored.limits.max_total_tokens == Limits().max_total_tokens - 8000
    assert restored.manifest['limits']['max_total_tokens'] == Limits().max_total_tokens
    fresh = Flaky()
    final = run(restored, fresh)
    assert fresh.seen[0] is None  # the rerun starts a fresh segment
    # The failed call counts as a decision, so decision 3 runs again and the cap of 4 ends the run there.
    assert final['stop_reason'] == 'model_call_budget'
    assert (final['usage']['calls'], final['actions'], final['usage']['input_tokens']) == (4, 3, 30)
    assert final['usage']['unreported_token_reserve'] == 8000 and final['usage']['accounting_complete'] is False
    assert [line['index'] for line in read(root, 'decisions.jsonl')] == [1, 2, 3]
    result = json.loads((root / 'result.json').read_text())
    assert [line['set_aside'] for line in result['provider_errors']] == ['provider-error-01']
    assert not (root / 'pending.json').exists()


def test_a_reopen_cut_short_is_finished_by_the_next_one(tmp_path, monkeypatch):
    session, rom = start(tmp_path)
    root = session.output
    run(session, Flaky(failures={4: 1}, reply=True))
    finish = recovery._finish_set_aside

    def cut(root, marker):
        raise OSError('power cut')
    monkeypatch.setattr(recovery, '_finish_set_aside', cut)
    with pytest.raises(OSError):
        reopen(rom, root)
    # The marker is written first, so the reserve is charged however the moves end. Resume waits for them.
    assert json.loads((root / 'pending.json').read_text())['phase'] == UNCERTAIN
    with pytest.raises(ValueError, match='does not match its checkpoint'):
        resume(rom, root, engine_factory=factory)
    monkeypatch.setattr(recovery, '_finish_set_aside', finish)
    attempt = reopen(rom, root)
    assert (attempt / 'result.json').is_file() and not (root / 'result.json').exists()
    assert json.loads((root / 'pending.json').read_text())['token_reserve'] == DEFAULT_RESERVE
    assert len(read(root, 'provider-errors.jsonl')) == 1
    resume(rom, root, engine_factory=factory).close()


def smoke_suite(tmp_path, monkeypatch, outage, *, reply=False, limits=Limits(max_model_calls=4)):
    """The smoke suite with its first task played by Flaky, which fails at the frames in outage."""
    smoke = quick_run.SUITES['smoke'][2]
    root = tmp_path / 'data'
    (root / 'game-data').mkdir(parents=True)
    (root / 'game-data' / 'current.json').write_text('{}')
    rom = tmp_path / 'red.gb'
    rom.write_bytes(b'rom')
    (root / 'setup.json').write_text(json.dumps({'rom': str(rom)}))
    rows = []
    for task in smoke:
        folder = root / 'fixtures' / task
        folder.mkdir(parents=True)
        write_json(folder / 'scenario.json', {'state_sha256': 'state-' + task, 'catalog_sha256': 'spec-' + task})
        rows.append({'id': task, 'category': task.split('-')[0], 'mode': catalog_batch.task_definition(task)['mode'],
                     'runnable': True, 'variants': [{'variant': 'default', 'path': str(folder)}]})
    listing = {'tasks': rows, 'runnable': len(rows)}
    for module in (catalog_batch, quick_run):
        monkeypatch.setattr(module, 'inventory', lambda fixtures: listing)
    monkeypatch.setattr(catalog_execution, 'select_scenario', lambda fixtures, task, variant: fixtures / task)
    monkeypatch.chdir(tmp_path)
    cut = smoke[0]

    class Provider(Flaky):
        def __init__(self, model=None, *, reasoning_effort='low', **extra):
            super().__init__(model, reasoning_effort=reasoning_effort, failures=outage, reply=reply)

    def run_task(fixtures, task, rom, game_data, output, **options):
        if task != cut:
            output.mkdir(parents=True)
        usage = {'input_tokens': 900, 'output_tokens': 100, 'calls': 1}
        if task != cut:
            write_json(output / 'result.json', {'state': 'finished', 'score': 1, 'score_max': 1, 'usage': usage})
        else:
            session = Session(FakeEngine(), output, {'rom_sha256': digest(rom.read_bytes())},
                              limits=limits, clock=lambda: 100)
            run(session, Provider(options['model'], reasoning_effort=options['reasoning_effort']))

    monkeypatch.setattr(catalog_batch, 'run_task', run_task)
    monkeypatch.setattr('pokeagent_bench.claude_provider.ClaudeCodeProvider', Provider)
    monkeypatch.setattr('pokeagent_bench.game.RedEngine', factory)
    words = ['pokebench', 'run', '--model', 'claude-sonnet-5-5', '--suite', 'smoke', '--output', 'out']
    monkeypatch.setattr('sys.argv', words)
    return smoke, cut


def test_rerunning_the_suite_command_finishes_a_cell_cut_by_a_provider_error(tmp_path, monkeypatch, capsys):
    """The proof: inject a provider error mid task, then run the same command again and the cell finishes."""
    outage = {4: 9}  # every attempt at decision 3 fails during the first command
    smoke, cut = smoke_suite(tmp_path, monkeypatch, outage)
    # The suite stopped short, so a script sees exit 1. The same command resumes it.
    with pytest.raises(SystemExit) as stopped:
        main()
    assert stopped.value.code == 1
    text = capsys.readouterr().out
    assert f'{cut} paused after a provider error with no model reply' in text
    assert 'Not every run finished' in text
    cell = next(path for path in sorted((tmp_path / 'out').glob('cell-*'))
                if (path / 'result.json').is_file() and (path / 'recovery.json').is_file())
    assert json.loads((cell / 'result.json').read_text())['state'] == 'paused'
    outage.clear()  # the provider is back
    assert main() == 0
    text = capsys.readouterr().out
    assert f'Resuming {cut} from its checkpoint.' in text
    assert f'Finished {len(smoke)} of {len(smoke)} runs' in text
    result = json.loads((cell / 'result.json').read_text())
    assert result['state'] == 'finished' and result['stop_reason'] == 'model_call_budget'
    assert result['usage']['calls'] == 4 and len(result['provider_errors']) == 4
    report = json.loads((tmp_path / 'out' / 'report.json').read_text())
    assert next(row for row in report['cells'] if row['task_id'] == cut)['provider_errors'] == 4


def test_rerunning_the_suite_command_resumes_a_cell_stopped_by_a_provider_error(tmp_path, monkeypatch, capsys):
    """A provider error after a model reply: the same command resumes the cell, no folder moved by hand."""
    outage = {4: 2}  # decision 3 fails after a model reply in each of the first two commands
    smoke, cut = smoke_suite(tmp_path, monkeypatch, outage, reply=True,
                             limits=Limits(max_model_calls=6, max_total_tokens=200_000))
    out = tmp_path / 'out'
    with pytest.raises(SystemExit) as stopped:
        main()
    assert stopped.value.code == 1
    text = capsys.readouterr().out
    assert f'{cut} stopped on a provider error. Its checkpoint is kept and the same command resumes it' in text
    assert 'Delete' not in text
    # The later tasks wait, so one provider outage cannot fail the rest of the suite.
    [cell] = sorted(out.glob('cell-*'))
    assert json.loads((cell / 'result.json').read_text())['stop_reason'] == 'provider_error'
    # The provider fails again on the rerun. The command stops instead of trying the decision a third time.
    assert main() == 2
    captured = capsys.readouterr()
    assert f'Resuming {cut} from its checkpoint after a provider error' in captured.out
    assert f'{cut} stopped on a provider error again' in captured.err
    assert [path.name for path in cell.glob('provider-error-*')] == ['provider-error-01']
    outage.clear()  # the provider is back
    assert main() == 0
    text = capsys.readouterr().out
    assert 'provider-error-02' in text
    assert f'Finished {len(smoke)} of {len(smoke)} runs' in text
    result = json.loads((cell / 'result.json').read_text())
    assert result['state'] == 'finished' and result['stop_reason'] == 'model_call_budget'
    # Two failed calls and four played decisions fill the cap of six. Each failed call is charged the reserve.
    assert (result['usage']['calls'], result['actions']) == (6, 4)
    assert result['usage']['unreported_token_reserve'] == 2 * DEFAULT_RESERVE
    assert [row['set_aside'] for row in result['provider_errors']] == ['provider-error-01', 'provider-error-02']
    assert json.loads((cell / 'manifest.json').read_text())['limits']['max_total_tokens'] == 200_000
    for attempt in ('provider-error-01', 'provider-error-02'):
        assert json.loads((cell / attempt / 'result.json').read_text())['stop_reason'] == 'provider_error'
    row = next(row for row in json.loads((out / 'report.json').read_text())['cells'] if row['task_id'] == cut)
    assert row['state'] == 'finished' and row['accounting_complete'] is False
