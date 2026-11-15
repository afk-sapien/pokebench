"""Ctrl-C pauses at the next decision boundary and never scores a partial run. No model is called."""
import json
import signal
import time
from types import SimpleNamespace

import pytest

from conftest import FakeEngine
from pokeagent_bench import interrupts, runner
from pokeagent_bench.claude_provider import ClaudeCodeProvider
from pokeagent_bench.core import Limits, digest
from pokeagent_bench.providers import ProviderError
from pokeagent_bench.recovery import NO_REPLY, STOPPED, resume
from pokeagent_bench.runner import run
from pokeagent_bench.session import Session


def press():
    """What the terminal does on Ctrl-C, without sending a real signal."""
    interrupts._active.handle(signal.SIGINT, None)


class Model:
    """Answers like a model. Presses Ctrl-C during the call or fails with no reply at chosen frames."""
    provider = 'claude-code'
    model = 'claude-sonnet-5-5'
    harness = ClaudeCodeProvider.harness
    config_identity = {}
    prompt = 'test'
    reasoning_effort = 'low'

    def __init__(self, presses=None, failures=None):
        self.presses = presses or {}  # frame -> presses during that call
        self.failures = failures or {}  # frame -> failures left
        self.packet_baseline = None

    def decide(self, observation, *args):
        for _ in range(self.presses.pop(observation['frame'], 0)):
            press()
        if self.failures.get(observation['frame'], 0) > 0:
            self.failures[observation['frame']] -= 1
            raise ProviderError('Claude returned a synthetic provider error',
                                details={'kind': 'provider_error', 'status': 529, 'no_reply': True})
        self.packet_baseline = 'segment'
        return {'actions': [{'button': 'wait', 'hold_frames': 2, 'release_frames': 0}], 'notes': None}, {
            'input_tokens': 10, 'output_tokens': 5}, {}

    def close(self):
        pass


def factory(rom, state):
    engine = FakeEngine()
    engine.frame = int(state.decode().split('-')[-1])
    return engine


def start(tmp_path):
    rom = tmp_path / 'test.gb'
    rom.write_bytes(b'fake rom')
    session = Session(FakeEngine(), tmp_path / 'run', {'rom_sha256': digest(rom.read_bytes())},
                      limits=Limits(max_model_calls=4), clock=lambda: 100)
    return session, rom


def indices(root):
    return [json.loads(line)['index'] for line in (root / 'decisions.jsonl').read_text().splitlines()]


def test_one_press_pauses_after_the_decision_and_the_same_run_resumes(tmp_path, capsys):
    session, rom = start(tmp_path)
    root = session.output
    before = signal.getsignal(signal.SIGINT)
    paused = run(session, Model(presses={4: 1}))  # decision 3 starts at frame 4
    assert paused['state'] == 'paused'
    assert paused['usage']['calls'] == 3 and paused['usage']['accounting_complete']
    assert not (root / 'pending.json').exists()
    assert 'pausing after the current decision' in capsys.readouterr().err
    assert signal.getsignal(signal.SIGINT) == before
    final = run(resume(rom, root, engine_factory=factory), Model())
    assert final['stop_reason'] == 'model_call_budget'
    assert final['usage']['calls'] == 4 and final['usage']['input_tokens'] == 40
    assert indices(root) == [1, 2, 3, 4]


def test_a_second_press_during_a_model_call_stops_and_the_run_cannot_resume(tmp_path):
    session, rom = start(tmp_path)
    root = session.output
    stopped = run(session, Model(presses={4: 2}))
    assert stopped['state'] == 'paused' and stopped['usage']['accounting_complete'] is False
    assert json.loads((root / 'pending.json').read_text()) == {'decision': 3, 'phase': STOPPED}
    assert indices(root) == [1, 2]
    with pytest.raises(ValueError, match='Ctrl-C stopped decision 3 .* not scored. Delete'):
        resume(rom, root, engine_factory=factory)


def test_a_press_during_the_retry_wait_pauses_and_the_run_resumes(tmp_path, monkeypatch):
    session, rom = start(tmp_path)
    root = session.output
    monkeypatch.setattr(runner, 'RETRY_DELAYS', (600, 600, 600, 600))
    sleeps = []

    def sleep(seconds):
        sleeps.append(seconds)
        press()

    monkeypatch.setattr(runner, 'time', SimpleNamespace(monotonic=time.monotonic, sleep=sleep))
    began = time.monotonic()
    paused = run(session, Model(failures={4: 9}))
    assert time.monotonic() - began < 5 and sleeps == [1]
    assert paused['state'] == 'paused' and paused['usage']['accounting_complete']
    assert paused['usage']['calls'] == 2
    assert json.loads((root / 'pending.json').read_text()) == {'decision': 3, 'phase': NO_REPLY}
    monkeypatch.undo()
    final = run(resume(rom, root, engine_factory=factory), Model())
    assert final['stop_reason'] == 'model_call_budget' and final['usage']['calls'] == 4
    assert indices(root) == [1, 2, 3, 4]


def test_the_guard_is_shared_and_restored():
    before = signal.getsignal(signal.SIGINT)
    with interrupts.pause_on_interrupt() as outer:
        with interrupts.pause_on_interrupt() as inner:
            assert inner is outer
        assert signal.getsignal(signal.SIGINT) == outer.handle
        outer.handle(signal.SIGINT, None)
        assert outer.requested
        outer.handle(signal.SIGINT, None)  # outside a model call the second press only warns
        with pytest.raises(KeyboardInterrupt):
            outer.handle(signal.SIGINT, None)
    assert signal.getsignal(signal.SIGINT) == before and interrupts._active is None
