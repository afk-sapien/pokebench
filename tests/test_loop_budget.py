import json

from pokeagent_bench.core import Limits, digest
from pokeagent_bench.loop_budget import initial, update
from pokeagent_bench.recovery import resume
from pokeagent_bench.runner import run
from pokeagent_bench.session import Session
from test_runner import StubProvider
from test_recovery_memory import factory


def point(map_id=0, x=1):
    return {'map_id': map_id, 'x': x, 'y': 1}


def test_known_map_switches_do_not_reset_counter_but_new_locations_and_awards_do():
    state = initial()
    update(state, point(), [], 0, 0)
    update(state, point(1), [], 10, 1)
    assert update(state, point(), [], 20, 2)['tokens_without_progress'] == 10
    assert update(state, point(1), [], 30, 3)['tokens_without_progress'] == 20
    assert update(state, point(1, 2), [], 40, 4)['tokens_without_progress'] == 0
    assert update(state, point(1, 2), ['badge:boulder'], 50, 5)['tokens_without_progress'] == 0
    assert update(state, point(), ['badge:boulder'], 60, 6)['tokens_without_progress'] == 10


def fixed_location(engine):
    engine.structured = lambda labels=None: {'location': point(engine.state['map_id']), 'party': [], 'inventory': []}
    return engine


def test_runner_stops_cross_map_loop(tmp_path, engine):
    fixed_location(engine)
    engine.on_tick = lambda e: e.state.update(map_id=(e.frame // 2) % 2)
    session = Session(engine, tmp_path / 'loop', {}, limits=Limits(max_loop_tokens=30))
    result = run(session, StubProvider({'button': 'wait', 'hold_frames': 2, 'release_frames': 0, 'notes': None}))
    assert result['stop_reason'] == 'loop_token_budget'
    assert result['usage']['calls'] == 3
    assert json.loads((session.output / 'loop_budget.json').read_text())['tokens_without_progress'] == 30


def test_pause_resume_preserves_loop_counter(tmp_path, engine):
    fixed_location(engine)
    rom = tmp_path / 'fake.gb'
    rom.write_bytes(b'fake')
    session = Session(engine, tmp_path / 'resume', {'rom_sha256': digest(rom.read_bytes())}, limits=Limits(max_loop_tokens=45))
    provider = StubProvider({'button': 'wait', 'hold_frames': 2, 'release_frames': 0, 'notes': None})
    run(session, provider, pause_after_decisions=2)
    restored = resume(rom, session.output, engine_factory=lambda rom, data: fixed_location(factory(rom, data)))
    final = run(restored, provider)
    assert final['stop_reason'] == 'loop_token_budget'
    assert final['usage']['calls'] == 3
