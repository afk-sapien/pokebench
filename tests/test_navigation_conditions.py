import pytest
from pokeagent_bench.navigation_conditions import ADDRESS, BANK, EXPECTED, NO_ENCOUNTER, PROTOCOL, install, prepare


class Memory:
    def __init__(self):
        self.values = {(BANK, ADDRESS + i): v for i, v in enumerate(EXPECTED)}

    def __getitem__(self, key):
        bank, address = key
        if isinstance(address, slice):
            return [self.values[(bank, i)] for i in range(address.start, address.stop)]
        return self.values[key]

    def __setitem__(self, key, value):
        self.values[key] = value


class Engine:
    def __init__(self):
        self.memory = Memory()


def manifest():
    return {'navigation_condition': PROTOCOL, 'task_id': 'navigation-forest-crossing', 'tested_skill': 'navigation'}


def test_guarded_patch_is_navigation_only():
    engine = Engine()
    install(engine, {})
    assert bytes(engine.memory[BANK, ADDRESS:ADDRESS + 10]) == EXPECTED
    install(engine, manifest())
    assert bytes(engine.memory[BANK, ADDRESS:ADDRESS + 4]) == NO_ENCOUNTER
    with pytest.raises(ValueError, match='restricted'):
        install(Engine(), {**manifest(), 'task_id': 'battle-wild-basics'})
    altered = Engine()
    altered.memory[BANK, ADDRESS] = 0
    with pytest.raises(ValueError, match='does not match'):
        install(altered, manifest())


def test_offline_trainer_setup_does_not_solve_puzzles(monkeypatch):
    changed = []
    monkeypatch.setattr('pokeagent_bench.catalog_fixtures.set_event', lambda e, s, name, value: changed.append((name, value)))
    strategy = {'events': {'EVENT_BEAT_MT_MOON_EXIT_SUPER_NERD': 1, 'EVENT_BEAT_MT_MOON_1_TRAINER_0': 2,
                           'EVENT_GOT_DOME_FOSSIL': 3, 'EVENT_BEAT_BROCK': 4}}
    prepare(None, 'navigation-branching-cave', strategy)
    assert changed == [('EVENT_BEAT_MT_MOON_1_TRAINER_0', True), ('EVENT_BEAT_MT_MOON_EXIT_SUPER_NERD', True)]
