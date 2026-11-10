"""Fixture scripts build a PokeSim policy context that fits either checkout."""
from dataclasses import dataclass
import importlib.util
from pathlib import Path
import re
import sys

SCRIPTS = Path(__file__).parents[1] / 'scripts'


def _helper():
    sys.path.insert(0, str(SCRIPTS))
    try:
        spec = importlib.util.spec_from_file_location('prepare_pokesim_gym', SCRIPTS / 'prepare_pokesim_gym.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(SCRIPTS))
    return module.policy_context


@dataclass
class WallClockContext:
    """PokeSim before #435."""
    snapshot: object
    stuck_seconds: float
    real_time: float
    mem: object = None
    sp: int | None = None


@dataclass
class PlayClockContext:
    """PokeSim from #435 on."""
    snapshot: object
    clock: int = 0
    mem: object = None
    sp: int | None = None

    def __post_init__(self):
        if isinstance(self.mem, (int, float)):
            raise TypeError('PolicyContext takes (snapshot, clock, mem, sp)')


def test_play_clock_checkout_gets_frames_and_memory():
    memory = object()
    context = _helper()(PlayClockContext, 'snapshot', 1234, 5.5, memory)
    assert (context.snapshot, context.clock, context.mem, context.sp) == ('snapshot', 1234, memory, None)


def test_wall_clock_checkout_keeps_the_original_form():
    memory = object()
    context = _helper()(WallClockContext, 'snapshot', 1234, 5.5, memory)
    assert (context.stuck_seconds, context.real_time, context.mem) == (0, 5.5, memory)


def test_scripts_build_contexts_only_through_the_helper():
    direct = [path.name for path in SCRIPTS.glob('*.py')
              if re.search(r'(?<![\w.])PolicyContext\(', path.read_text())]
    assert direct == ['prepare_pokesim_gym.py']
