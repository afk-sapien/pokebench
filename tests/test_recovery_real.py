"""Opt-in real cartridge recovery checks. No model calls or distributed ROMs."""
import os
from pathlib import Path

import pytest

from pokeagent_bench.core import Limits
from pokeagent_bench.recovery import resume
from pokeagent_bench.runner import run
from pokeagent_bench.session import Session, load_engine, replay


@pytest.mark.parametrize('release_frames', [0, 8])
def test_real_emulator_queued_release_matches_uninterrupted(tmp_path, release_frames):
    rom_path = os.environ.get('POKEAGENT_TEST_ROM')
    scenario_path = os.environ.get('POKEAGENT_TEST_SCENARIO')
    if not rom_path or not scenario_path:
        pytest.skip('Set private ROM and scenario paths to run real recovery checks')
    rom = Path(rom_path)

    class Provider:
        provider = 'codex'
        model = 'scripted-input-release-test'
        visual_feedback = True
        compact_feedback = True

        def decide(self, observation, *args):
            command = ({'button': 'right', 'hold_frames': 16, 'release_frames': release_frames}
                       if observation['frame'] == 0 else
                       {'button': 'wait', 'hold_frames': 60, 'release_frames': 0})
            return {'actions': [command], 'notes': None}, {'input_tokens': 0, 'output_tokens': 0}, {}

        def close(self):
            pass

    traces = []
    for paused in (True, False):
        engine, manifest = load_engine(rom, Path(scenario_path))
        output = tmp_path / ('resumed' if paused else 'continuous')
        session = Session(engine, output, manifest, track='visual', goal='challenge',
                          limits=Limits(max_model_calls=2), clock=lambda: 100)
        run(session, Provider(), pause_after_decisions=1 if paused else None)
        if paused:
            session = resume(rom, output, clock=lambda: 100)
            run(session, Provider())
        traces.append(replay(rom, output)['trace_head'])
    assert traces[0] == traces[1]
    assert (tmp_path / 'resumed/final.state').read_bytes() == (tmp_path / 'continuous/final.state').read_bytes()
