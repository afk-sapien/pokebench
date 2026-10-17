"""Explicit battle-free conditions for isolated navigation evaluations."""
from pathlib import Path

from .core import digest

PROTOCOL = 'navigation-no-battles-v1'
AFFECTED = {
    'navigation-forest-crossing': ('VIRIDIAN_FOREST', 'ROUTE_3'),
    'navigation-branching-cave': ('MT_MOON', 'ROUTE_3', 'ROUTE_4'),
    'navigation-boulder-puzzle': ('VICTORY_ROAD', 'ROUTE_23'),
    'navigation-blocked-route-alternative': ('ROUTE_5', 'ROUTE_6'),
}
# Red TryDoWildEncounter: ld a,1 / and a / ret returns NZ (no encounter).
# The guard covers both initial native checks before any change is installed.
BANK = 4
ADDRESS = 0x7870
EXPECTED = bytes.fromhex('fa57cca7c0fa36d7a7c0')
NO_ENCOUNTER = bytes.fromhex('3e01a7c9')


def install(engine, manifest):
    condition = manifest.get('navigation_condition')
    if condition is None:
        return
    if (condition != PROTOCOL or manifest.get('task_id') not in AFFECTED
            or manifest.get('tested_skill') != 'navigation'):
        raise ValueError('Battle-free condition is restricted to registered navigation tasks')
    actual = bytes(engine.memory[BANK, ADDRESS:ADDRESS + len(EXPECTED)])
    if actual != EXPECTED:
        raise ValueError('Navigation encounter patch does not match the loaded Red ROM')
    for index, value in enumerate(NO_ENCOUNTER):
        engine.memory[BANK, ADDRESS + index] = value


def prepare(engine, task_id, strategy):
    """Clear only relevant trainer flags while constructing a private start."""
    from .catalog_fixtures import set_event
    names = sorted(name for name in strategy['events']
                   if name.startswith('EVENT_BEAT_')
                   and any(name.startswith('EVENT_BEAT_' + area + '_') for area in AFFECTED[task_id]))
    if not names:
        raise ValueError('No navigation trainer flags found')
    for name in names:
        set_event(engine, strategy, name, True)
    return {'protocol': PROTOCOL, 'defeated_trainer_events': names,
            'wild_encounters': 'disabled for the whole trial',
            'rom_patch': {'bank': BANK, 'address': ADDRESS,
                          'expected': EXPECTED.hex(), 'replacement': NO_ENCOUNTER.hex()},
            'implementation_sha256': digest(Path(__file__).read_bytes())}
