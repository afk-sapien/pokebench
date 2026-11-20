"""A provider error with no model reply spends nothing. It is retried, then the run pauses and the same command resumes it."""
import json

import pytest

from conftest import FakeEngine
from pokeagent_bench import catalog_batch, catalog_execution, quick_run, runner
from pokeagent_bench.claude_provider import ClaudeCodeProvider
from pokeagent_bench.cli import main
from pokeagent_bench.core import Limits, digest, write_json
from pokeagent_bench.providers import ProviderError
from pokeagent_bench.recovery import NO_REPLY, resume
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


def test_rerunning_the_suite_command_finishes_a_cell_cut_by_a_provider_error(tmp_path, monkeypatch, capsys):
    """The proof: inject a provider error mid task, then run the same command again and the cell finishes."""
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
    outage = {4: 9}  # every attempt at decision 3 fails during the first command
    cut = smoke[0]

    class Provider(Flaky):
        def __init__(self, model=None, *, reasoning_effort='low', **extra):
            super().__init__(model, reasoning_effort=reasoning_effort, failures=outage)

    def run_task(fixtures, task, rom, game_data, output, **options):
        if task != cut:
            output.mkdir(parents=True)
        usage = {'input_tokens': 900, 'output_tokens': 100, 'calls': 1}
        if task != cut:
            write_json(output / 'result.json', {'state': 'finished', 'score': 1, 'score_max': 1, 'usage': usage})
        else:
            session = Session(FakeEngine(), output, {'rom_sha256': digest(rom.read_bytes())},
                              limits=Limits(max_model_calls=4), clock=lambda: 100)
            run(session, Provider(options['model'], reasoning_effort=options['reasoning_effort']))

    monkeypatch.setattr(catalog_batch, 'run_task', run_task)
    monkeypatch.setattr('pokeagent_bench.claude_provider.ClaudeCodeProvider', Provider)
    monkeypatch.setattr('pokeagent_bench.game.RedEngine', factory)
    words = ['pokebench', 'run', '--model', 'claude-sonnet-5-5', '--suite', 'smoke', '--output', 'out']
    monkeypatch.setattr('sys.argv', words)
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
