import json

from pokeagent_bench.core import Limits, digest
from pokeagent_bench.loop_budget import initial, milestone_gap, update
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


def test_milestone_gap_counts_from_the_latest_stamped_award():
    assert milestone_gap({}, 40, 3)['tokens_without_milestone'] == 40
    awards = {'town:viridian': {'tokens': 25, 'decision': 2}, 'starter': {'tokens': 10, 'decision': 1}}
    gap = milestone_gap(awards, 70, 5)
    assert (gap['tokens_without_milestone'], gap['last_milestone_decision'], gap['milestones']) == (45, 2, 2)


class AwardingProvider(StubProvider):
    """Each call spends 15 tokens. The listed calls earn one milestone stamped like a campaign award."""

    def __init__(self, session, award_calls):
        super().__init__({'button': 'wait', 'hold_frames': 2, 'release_frames': 0, 'notes': None})
        self.session, self.award_calls, self.calls = session, award_calls, 0

    def decide(self, *args):
        self.calls += 1
        if self.calls in self.award_calls:
            used = self.session.usage['input_tokens'] + self.session.usage['output_tokens'] + 15
            self.session.evaluator.awarded[f'm{self.calls}'] = {'points': 0, 'tokens': used, 'decision': self.calls}
        return super().decide(*args)


def test_runner_stops_after_the_milestone_gap_and_names_that_guard(tmp_path, engine):
    session = Session(engine, tmp_path / 'gap', {}, limits=Limits(max_milestone_tokens=45))
    result = run(session, AwardingProvider(session, ()))
    assert (result['stop_reason'], result['usage']['calls']) == ('milestone_token_budget', 3)
    saved = json.loads((session.output / 'milestone_budget.json').read_text())
    assert (saved['tokens_without_milestone'], saved['limit']) == (45, 45)
    assert not (session.output / 'loop_budget.json').exists()


def test_a_new_milestone_restarts_the_count_and_the_count_survives_a_resume(tmp_path, engine):
    rom = tmp_path / 'fake.gb'
    rom.write_bytes(b'fake')
    session = Session(engine, tmp_path / 'resume', {'rom_sha256': digest(rom.read_bytes())},
                      limits=Limits(max_milestone_tokens=45))
    provider = AwardingProvider(session, (2,))
    run(session, provider, pause_after_decisions=3)
    restored = resume(rom, session.output, engine_factory=factory)
    provider.session = restored
    final = run(restored, provider)
    # The award at call 2 was stamped at 30 tokens, so the guard fires at 75 tokens, after call 5.
    assert (final['stop_reason'], final['usage']['calls']) == ('milestone_token_budget', 5)
    assert json.loads((restored.output / 'milestone_budget.json').read_text())['last_milestone_decision'] == 2
