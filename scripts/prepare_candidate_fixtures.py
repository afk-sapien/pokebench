"""Build the candidate task starts in a private directory. No model calls.

Each start loads a released League source or a saved adventure state, then writes an explicit
party, bag, money, badges, event flags and the few raw RAM bytes each recipe lists. Nothing
is written during evaluation. Two builds of one recipe give the same state digest.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from pokeagent_bench.catalog_fixtures import (
    command, load_source, read, save, set_bag, set_event, set_party, snapshot, walk_to,
)
from pokeagent_bench.core import digest, write_json
from pokeagent_bench.evaluation_catalog import load_candidates
from pokeagent_bench.navigation_conditions import AFFECTED, prepare
from pokecore.gen1 import W_BADGES


def mon(species, level, moves):
    return {'species': species, 'level': level, 'moves': moves}


# The released Elite Four moves. No one-hit knockout, fixed-damage, Hyper Beam or Explosion moves.
JOLTEON = ('JOLTEON', [85, 87, 24, 98])
ALAKAZAM = ('ALAKAZAM', [94, 60, 105, 115])
LAPRAS = ('LAPRAS', [58, 57, 34, 85])
RHYDON = ('RHYDON', [89, 157, 34, 30])
VENUSAUR = ('VENUSAUR', [75, 72, 34, 79])
# The lowest level from 50 up at which the careful reference wins with no faint. 50 to 54 lose.
ELITE_FOUR_LEVEL = 55
CHAMPION_LEVEL = 60
# Native Red RAM written at construction only.
STATUS_FLAGS1 = 0xD728
GAVE_SAFFRON_GUARDS_DRINK = 0x40
SAFARI_STEPS = 0xD70D
SAFARI_BALLS = 0xDA47
FIRST_LOCK_CAN = 0xD743
NUM_BOX_ITEMS = 0xD53A
# Badge bits: Boulder, Cascade, Thunder, Rainbow, Soul, Marsh, Volcano, Earth.
BOULDER_CASCADE = 0b11
ALL_BADGES = 0xFF
# The first lock is under the top can of the middle column, index 6 = column 2 * 3 + row 0, at (5, 7).
# Vermilion City rolls Random & $e on entry, so the native index is always even.
VERMILION_FIRST_CAN = 6
SAFARI_START_STEPS = 500
SAFARI_START_BALLS = 30

RECIPES = {
    'navigation-vermilion-gym-switches': {
        'archive': 240, 'map_id': 92, 'position': (4, 17),
        'party': [mon('WARTORTLE', 25, [33, 39, 145, 55])], 'bag': [], 'money': 0, 'badges': BOULDER_CASCADE,
        'events': {'EVENT_1ST_LOCK_OPENED': False, 'EVENT_2ND_LOCK_OPENED': False, 'EVENT_BEAT_LT_SURGE': False},
        'memory': [[FIRST_LOCK_CAN, VERMILION_FIRST_CAN]]},
    'navigation-safari-zone-secret-house': {
        'archive': 600, 'map_id': 220, 'position': (15, 25),
        'party': [mon('NIDOKING', 50, [24, 30, 40, 34])], 'bag': [], 'money': 200,
        'events': {'EVENT_IN_SAFARI_ZONE': True, 'EVENT_SAFARI_GAME_OVER': False, 'EVENT_GOT_HM03': False},
        'memory': [[SAFARI_STEPS, SAFARI_START_STEPS >> 8], [SAFARI_STEPS + 1, SAFARI_START_STEPS & 0xFF],
                   [SAFARI_BALLS, SAFARI_START_BALLS]]},
    'objectives-saffron-gate-drink': {
        'archive': 558, 'map_id': 76, 'position': (1, 4),
        'party': [mon('JOLTEON', 40, [85, 24, 98, 86])], 'bag': [], 'money': 500, 'pc_items': [],
        'clear_bits': [[STATUS_FLAGS1, GAVE_SAFFRON_GUARDS_DRINK]]},
    'battle-elite-four-no-items-no-faint': {
        'source': 'data/red-ability-v4/fixtures/league', 'map_id': 245,
        'party': [mon(name, ELITE_FOUR_LEVEL, moves) for name, moves in (JOLTEON, ALAKAZAM, LAPRAS, RHYDON, VENUSAUR)],
        'bag': [], 'money': 0},
    'battle-champion-no-items-no-faint': {
        'source': 'data/decision-v1-sources-v2/champion', 'map_id': 120,
        'party': [mon(name, CHAMPION_LEVEL, moves) for name, moves in (JOLTEON, ALAKAZAM, LAPRAS)],
        'bag': [], 'money': 0, 'battle': True},
}


def build(args, key, entry, strategy):
    recipe = RECIPES[key]
    if 'source' in recipe:
        source = args.root / recipe['source'] / 'initial.state'
        engine, provenance = load_source(args.rom, source, 0)
    else:
        engine, provenance = load_source(args.rom, args.archive / f'event-{recipe["archive"]}.state', 90)
    trace = []
    try:
        if 'walk' in recipe:
            trace.extend(walk_to(engine, *recipe['walk'], limit=2000))
        set_party(engine, strategy, recipe['party'])
        set_bag(engine, recipe['bag'], recipe['money'])
        if 'pc_items' in recipe:
            # Native Red wNumBoxItems and wBoxItems, not Pokemon storage.
            engine.memory[NUM_BOX_ITEMS] = len(recipe['pc_items'])
            for index, (item, quantity) in enumerate(recipe['pc_items']):
                engine.memory[NUM_BOX_ITEMS + 1 + 2 * index] = item
                engine.memory[NUM_BOX_ITEMS + 2 + 2 * index] = quantity
            engine.memory[NUM_BOX_ITEMS + 1 + 2 * len(recipe['pc_items'])] = 255
        for name, value in recipe.get('events', {}).items():
            set_event(engine, strategy, name, value)
        if 'badges' in recipe:
            engine.memory[W_BADGES] = recipe['badges']
        for address, mask in recipe.get('clear_bits', []):
            engine.memory[address] = engine.memory[address] & ~mask
        for address, value in recipe.get('memory', []):
            engine.memory[address] = value
        if recipe.get('battle'):
            for action in read(args.root / recipe['source'] / 'entry-commands.json'):
                trace.append(command(engine, action['button'], action['hold_frames'], action['release_frames']))
            for _ in range(100):
                if snapshot(engine)['ui'] == 'battle_menu':
                    break
                trace.append(command(engine, 'a'))
            else:
                raise ValueError('Could not reach the first battle menu')
        state = engine.structured()
        expected = {'map_id': recipe['map_id'], 'ui': 'battle_menu' if recipe.get('battle') else 'overworld',
                    'party': state['party'], 'inventory': state['inventory'], 'money': recipe['money']}
        if 'position' in recipe:
            expected['position'] = list(recipe['position'])
        provenance['offline_setup'] = recipe
        provenance['setup_writes'] = ('Own party, bag, money, PC items, badges, explicitly listed event flags and '
                                      'explicitly listed RAM bytes only. No writes during evaluation.')
        if key in AFFECTED:
            provenance['navigation_setup'] = prepare(engine, key, strategy)
        provenance['setup_commands'] = trace
        provenance['builder_sha256'] = digest(Path(__file__).read_bytes())
        return save(engine, args.rom, entry, args.output / key, provenance, expected)
    finally:
        engine.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True, help='Private benchmark data root with the League sources')
    parser.add_argument('--archive', type=Path, required=True, help='Saved adventure states directory')
    parser.add_argument('--rom', type=Path, required=True)
    parser.add_argument('--game-data', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--tasks', nargs='+')
    args = parser.parse_args()
    current = read(args.game_data / 'current.json')['bundle']
    strategy = read(args.game_data / 'bundles' / current / 'strategy.json')
    entries = {task['id']: task for group in load_candidates() for task in group['evals']}
    args.output.mkdir(parents=True, exist_ok=True)
    report = {}
    for key in args.tasks or sorted(RECIPES):
        report[key] = build(args, key, entries[key], strategy)
        print('Built', key, flush=True)
    write_json(args.output / 'candidate-build.json', report)


if __name__ == '__main__':
    main()
