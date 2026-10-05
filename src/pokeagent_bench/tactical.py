"""Public fixture specification, without a strategy or opponent decision oracle."""
from pokesim_core.gen1 import read_bag, read_party

TEAM = [(110, 45, (95, 133, 57, 156)),
        (84, 45, (85, 86, 98, 97)),
        (147, 45, (95, 138, 101, 109))]
TEAM_V2 = [(111, 50, (95, 133, 57, 156)),
           (84, 45, (84, 86, 98, 97)),
           (147, 45, (95, 138, 101, 109))]
TIMING_OFFSETS = (0, 17, 37, 67, 97)


def validate_team(memory, version=1):
    if version not in (1, 2):
        raise ValueError('Unknown tactical team version')
    expected = TEAM if version == 1 else TEAM_V2
    party = read_party(memory)
    if [(m['species'], m['level'], tuple(m['moves'])) for m in party] != expected:
        raise ValueError('Tactical fixture party differs from the registered team')
    if any(m['hp'] != m['max_hp'] or m['status'] for m in party):
        raise ValueError('Tactical fixture requires a healthy starting party')
    if tuple(read_bag(memory)) != ((82, 1),):
        raise ValueError('Tactical fixture permits exactly one Elixer')
