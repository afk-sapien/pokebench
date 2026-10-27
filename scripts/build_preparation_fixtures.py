"""Build private native preparation starts without running any models.

Party edits are offline fixture setup only. Every evaluated preparation action
uses Core's native controller machines. Opponent assessment bindings are stored
separately and must be smoke-tested before publishing model scores.
"""
import argparse
import json
from pathlib import Path

from pokecore.gen1 import W_PARTY_MONS, read_party
from pokecore.shortcuts import current_screen

from pokeagent_bench.catalog_fixtures import (
    command, load_source, save, set_active_box, set_bag, set_party, set_event, walk_to,
)
from pokeagent_bench.core import digest, write_json
from pokeagent_bench.evaluation_catalog import load_catalog


def mon(species, level, moves, **kw):
    return dict(species=species, level=level, moves=list(moves), **kw)


BROCK = [mon('SQUIRTLE', 15, [145, 33, 39, 55]), mon('PIDGEY', 12, [16, 28, 98])]
LEAGUE = [mon('JOLTEON', 55, [85, 86, 24, 42]), mon('LAPRAS', 55, [57, 58, 109, 34]),
          mon('SNORLAX', 55, [34, 89, 156, 133])]
PP = [mon('POLIWRATH', 50, [95, 133, 57, 156], pp=[20, 20, 4, 10]),
      mon('KADABRA', 50, [94, 105, 115, 134], pp=[5, 20, 20, 15])]
TEAMS = {
    'lead-selection': BROCK,
    'recovery-before-continuing': BROCK,
    'assemble-storage-roster': [mon('CHARIZARD', 50, [53, 163, 19, 108]),
                                mon('PIDGEOT', 48, [17, 19, 98, 28])],
    'shop-for-challenge': [mon('PIKACHU', 20, [84, 98, 86, 45]),
                           mon('BULBASAUR', 20, [22, 33, 73, 45])],
    'move-replacement-across-fights': [mon('KADABRA', 50, [94, 105, 115, 134]),
                                       mon('POLIWRATH', 50, [95, 133, 57, 156])],
    'scarce-tm-allocation': [mon('PIKACHU', 45, [84, 86, 98, 97]),
                            mon('JOLTEON', 45, [84, 86, 24, 42]),
                            mon('LAPRAS', 45, [57, 58, 109, 34])],
    'damaged-team-rescue': [mon('JYNX', 55, [58, 94, 142, 156], hp=35, pp=[0, 10, 10, 10]),
                           mon('SNORLAX', 40, [34, 133, 156, 29], hp=0),
                           mon('JOLTEON', 55, [85, 86, 42, 97], hp=0)],
    'uncertain-opponent': LEAGUE,
    'pp-allocation-gauntlet': PP,
    'scarce-resource-league': LEAGUE,
}
BAGS = {
    'lead-selection': [(20, 2)], 'recovery-before-continuing': [(20, 1)],
    'assemble-storage-roster': [(18, 2)], 'shop-for-challenge': [],
    'move-replacement-across-fights': [(206, 1), (245, 1), (82, 1)],
    'scarce-tm-allocation': [(224, 1), (82, 1)],
    'damaged-team-rescue': [(53, 1), (17, 2), (82, 1)],
    'uncertain-opponent': [(18, 2), (16, 1)], 'pp-allocation-gauntlet': [(82, 1)],
    'scarce-resource-league': [(18, 1), (82, 1)],
}
BOX = [mon('JOLTEON', 50, [85, 86, 24, 42]), mon('JYNX', 50, [94, 58, 142, 156]),
       mon('SNORLAX', 50, [34, 156, 133, 89]), mon('LAPRAS', 50, [57, 58, 109, 34])]


def raw(button, hold=8, release=24):
    return {'button': button, 'hold_frames': hold, 'release_frames': release}


def do(engine, action):
    command(engine, action['button'], action['hold_frames'], action['release_frames'])


def reach_menu(engine, target):
    commands = []
    for _ in range(30):
        if current_screen(engine.memory, version='red') == target:
            return commands
        action = raw('a', 8, 60)
        commands.append(action)
        do(engine, action)
    raise ValueError(f'Did not reach native {target} menu')


def build(args):
    reference = Path(args.game_data)
    bundle = json.loads((reference / 'current.json').read_text())['bundle']
    strategy = json.loads((reference / 'bundles' / bundle / 'strategy.json').read_text())
    entries = load_catalog('preparation')[0]['evals']
    results = {}
    for entry in entries:
        key = entry['id'].removeprefix('preparation-')
        event = 18 if key == 'assemble-storage-roster' else 67 if key == 'shop-for-challenge' else 760 if key == 'scarce-resource-league' else 66
        source = Path(args.states) / f'event-{event}.state'
        engine, provenance = load_source(args.rom, source, settle=90)
        try:
            set_party(engine, strategy, TEAMS[key])
            set_bag(engine, BAGS[key], 900 if key == 'shop-for-challenge' else 3000 if key == 'scarce-resource-league' else 0)
            if key == 'recovery-before-continuing':
                for slot, member in enumerate(read_party(engine.memory)):
                    hp = member['max_hp'] // 2
                    engine.memory[W_PARTY_MONS + 44*slot + 1] = hp >> 8
                    engine.memory[W_PARTY_MONS + 44*slot + 2] = hp & 255
            setup = []
            facilities = {}
            if key == 'assemble-storage-roster':
                set_active_box(engine, strategy, BOX)
                setup.extend(walk_to(engine, 13, 4))
                do(engine, raw('up'))
                setup.append(raw('up'))
                # Fixture ends at the native PC menu. Re-entry from this tile is mechanical.
                setup.extend(reach_menu(engine, 'pc'))
                facilities['pc'] = [raw('up')] + [raw('a', 8, 60)] * 3
            elif key in ('shop-for-challenge', 'scarce-resource-league'):
                setup.extend(walk_to(engine, 2, 5))
                do(engine, raw('left'))
                setup.append(raw('left'))
                setup.extend(reach_menu(engine, 'mart'))
                facilities['shop'] = [raw('left')] + [raw('a', 8, 60)] * 3
            elif key == 'recovery-before-continuing':
                setup.extend(walk_to(engine, 3, 3))
                do(engine, raw('up'))
                setup.append(raw('up'))
                before = engine.save()
                heal = []
                healed = False
                for _ in range(100):
                    action = raw('a', 8, 60)
                    heal.append(action)
                    do(engine, action)
                    party = read_party(engine.memory)
                    healed = all(m['hp'] == m['max_hp'] and not m['status'] for m in party)
                    if healed and current_screen(engine.memory, version='red') == 'overworld':
                        break
                if not healed:
                    raise ValueError('Native Center recovery reference failed')
                engine.load(before)
                facilities['heal_at_center'] = heal
            elif key in ('damaged-team-rescue', 'pp-allocation-gauntlet',
                         'move-replacement-across-fights', 'uncertain-opponent', 'scarce-tm-allocation'):
                # Preparation environment is disclosed as a safe Center room.
                # The private assessment later places the frozen team before its target.
                pass
            provenance.update(builder_sha256=digest(Path(__file__).read_bytes()),
                              offline_party=TEAMS[key], offline_bag=BAGS[key],
                              setup_commands=setup, setup_memory_writes='Party, box and bag only before trial')
            destination = Path(args.output) / entry['id']
            info = save(engine, args.rom, entry, destination, provenance,
                        {'battle': {'kind': 'none'}, 'money': 900 if key == 'shop-for-challenge' else 3000 if key == 'scarce-resource-league' else 0})
            manifest = json.loads((destination / 'scenario.json').read_text())
            manifest.update(input_policy='release-all-before-first-tick-v1', objective={'kind': 'preparation-submission', 'task_id': entry['id'],
                                      'description': entry['agent_goal']},
                            preparation={'facilities': facilities, 'slot_indexing': 'zero-based',
                                         'assessment': 'Frozen party is transferred to isolated target checkpoints'})
            write_json(destination / 'scenario.json', manifest)
            results[entry['id']] = info
            print(entry['id'], 'start checked', flush=True)
        finally:
            engine.close()
    write_json(Path(args.output) / 'preparation-bindings.json', results)
    return results



def build_targets(args):
    from pokeagent_bench.core import core_provenance, emulator_manifest
    from pokeagent_bench.gameplay import ui_state
    target_root = Path(args.output) / 'preparation-assessment-targets'
    sources = Path(args.decision_sources)
    reference = Path(args.game_data)
    bundle = json.loads((reference / 'current.json').read_text())['bundle']
    strategy = json.loads((reference / 'bundles' / bundle / 'strategy.json').read_text())
    definitions = {
        'brock': (Path(args.states) / 'event-68.state', (4, 2), 'up', 34, 'badge:boulder'),
        'misty': (Path(args.states) / 'event-173.state', (4, 3), 'up', 35, 'badge:cascade'),
        'lorelei': (sources / 'lorelei/initial.state', None, None, 44, 'elite:lorelei'),
        'bruno': (sources / 'bruno/initial.state', None, None, 33, 'elite:bruno'),
        'agatha': (sources / 'agatha/initial.state', None, None, 46, 'elite:agatha'),
        'lance': (sources / 'lance-stable/initial.state', None, None, 47, 'elite:lance'),
        'champion-a': (Path(args.states) / 'event-786.state', None, None, 43, 'champion'),
        'champion-b': (Path(args.states) / 'event-786.state', None, None, 43, 'champion'),
        'champion-c': (Path(args.states) / 'event-786.state', None, None, 43, 'champion'),
    }
    built = {}
    for name, (source, position, facing, trainer, target) in definitions.items():
        destination = target_root / name
        if (destination / 'scenario.json').exists():
            existing = json.loads((destination / 'scenario.json').read_text())
            existing['input_policy'] = 'release-all-before-first-tick-v1'
            write_json(destination / 'scenario.json', existing)
            built[name] = {'id': name, 'scenario': str(destination), 'objective': existing['objective'],
                           'entry_commands': json.loads((destination / 'entry-commands.json').read_text())}
            continue
        engine, provenance = load_source(args.rom, source, settle=90 if name in ('brock', 'misty') else 0)
        try:
            if name == 'misty':
                flags = ['EVENT_BEAT_CERULEAN_GYM_TRAINER_0', 'EVENT_BEAT_CERULEAN_GYM_TRAINER_1']
                for flag in flags:
                    set_event(engine, strategy, flag, True)
                provenance['offline_unrelated_trainers_cleared'] = flags
            if name.startswith('champion-'):
                starter = {'champion-a': 177, 'champion-b': 153, 'champion-c': 176}[name]
                engine.memory[0xD715] = starter
                provenance['offline_rival_starter_branch'] = starter
            if position:
                provenance['approach'] = walk_to(engine, *position)
                do(engine, raw(facing))
            state = engine.save()
            screen = engine.screenshot()
            commands = [raw('up', 16, 16)] * 2 if name == 'lance' else []
            for action in commands:
                do(engine, action)
            for _ in range(200):
                if engine.memory[0xD057] == 2 and ui_state(engine.memory)['kind'] == 'battle_menu':
                    break
                action = raw('a', 8, 24)
                commands.append(action)
                do(engine, action)
            if engine.memory[0xD057] != 2 or engine.memory[0xD031] != trainer:
                raise ValueError(f'{name}: native trainer entry failed')
            # Keep native loaded trainer roster as private assessment evidence.
            opponent = list(engine.memory[0xD89C:0xD8A4])
            engine.load(state)
            destination = target_root / name
            destination.mkdir(parents=True, exist_ok=False)
            (destination / 'initial.state').write_bytes(state)
            (destination / 'preview.png').write_bytes(screen)
            objective = {'kind': 'guarded-milestones', 'targets': [target], 'no_faints': False,
                         'description': f'Defeat {name} with the frozen prepared team'}
            write_json(destination / 'scenario.json', {
                'format': 1, 'game': 'red', 'name': name, 'rom_sha256': digest(Path(args.rom).read_bytes()),
                'state_sha256': digest(state), 'preview_sha256': digest(screen),
                'core': core_provenance(), **emulator_manifest(), 'objective': objective,
                'input_policy': 'release-all-before-first-tick-v1',
                'provenance': provenance, 'trainer_entry_checked': True,
                'trainer_class': trainer, 'native_opponent_party_bytes': opponent,
            })
            write_json(destination / 'entry-commands.json', commands)
            built[name] = {'id': name, 'scenario': str(destination),
                           'objective': objective, 'entry_commands': commands}
            print(name, 'native trainer entry checked', opponent, flush=True)
        finally:
            engine.close()
    rosters = [tuple(json.loads((target_root / ('champion-' + letter) / 'scenario.json').read_text())['native_opponent_party_bytes'])
               for letter in ('a', 'b', 'c')]
    if len(set(rosters)) != 3:
        raise ValueError('Champion native starter branches did not produce three distinct rosters')
    schedules = {
        'lead-selection': ['brock'], 'recovery-before-continuing': ['brock'],
        'assemble-storage-roster': ['lorelei'], 'shop-for-challenge': ['misty'],
        'move-replacement-across-fights': ['lorelei', 'bruno'], 'scarce-tm-allocation': ['lorelei'],
        'damaged-team-rescue': ['lance'], 'uncertain-opponent': ['champion-a'],
        'pp-allocation-gauntlet': ['lorelei', 'bruno'],
        'scarce-resource-league': ['lorelei', 'bruno', 'agatha', 'lance', 'champion-a'],
    }
    bindings_path = Path(args.output) / 'preparation-bindings.json'
    bindings = json.loads(bindings_path.read_text())
    for key, schedule in schedules.items():
        task_id = 'preparation-' + key
        binding = bindings[task_id]
        binding.update(task_id=task_id, targets=[built[name] for name in schedule],
                       offsets=[0, 17, 37, 67, 97], threshold=None, calibration='pending')
        if key == 'uncertain-opponent':
            binding['target_variants'] = [[built['champion-' + letter]] for letter in ('a', 'b', 'c')]
    write_json(bindings_path, bindings)
    return bindings

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('rom', 'game-data', 'states', 'output', 'decision-sources'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--targets-only', action='store_true')
    args = parser.parse_args()
    if not args.targets_only:
        build(args)
    build_targets(args)


if __name__ == '__main__':
    main()
