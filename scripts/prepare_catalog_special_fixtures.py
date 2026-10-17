"""Construct native midbattle and opponent-variant catalog fixtures offline."""
from pathlib import Path
import argparse
import json
from pokeagent_bench.catalog_fixtures import read, load_source, set_party, set_bag, command, save
from pokeagent_bench.gameplay import ui_state
from pokeagent_bench.core import write_json
from pokesim_core.gen1 import W_RIVAL_STARTER, W_ENEMY_SPECIES2, W_ENEMY_LEVEL, W_IS_IN_BATTLE, W_TRAINER_CLASS, W_PARTY_MONS
from pokesim_core.shortcuts.actions import ChooseMove
from pokesim_core.shortcuts.machine import Done
from prepare_catalog_fixtures import mon, PIDGEY, PIKA

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom', type=Path, required=True)
    parser.add_argument('--root', type=Path, required=True, help='Private benchmark data root')
    parser.add_argument('--archive', type=Path, required=True, help='Saved adventure states directory')
    parser.add_argument('--game-data', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    rom, root, archive, private_root = (args.rom, args.output, args.archive, args.root)
    strategy = read(args.game_data / 'bundles' / read(args.game_data / 'current.json')['bundle'] / 'strategy.json')
    catalog = Path(__file__).resolve().parents[1] / 'src/pokeagent_bench/catalogs'
    entries = {e['id']: e for p in catalog.glob('*.json') for e in read(p)['evals']}

    def enter(e, trace):
        for _ in range(300):
            u = ui_state(e.memory)
            if u['kind'] == 'battle_menu':
                return
            trace.append(command(e, 'b' if u['kind'] in ('menu', 'move_menu') and e.memory[W_IS_IN_BATTLE] in (1, 2) else 'a'))
        raise ValueError('Battle entry did not settle')

    def export(key, e, prov, dest=None):
        result = save(e, rom, entries[key], dest or root / key, prov, {'ui': 'battle_menu', 'map_id': e.structured()['location']['map_id']})
        if dest is None:
            report = read(root / 'fixture-build.json')
            report['fixtures'][key] = result
            report['pending'].pop(key, None)
            write_json(root / 'fixture-build.json', report)
            write_json(root / 'bindings.json', report['fixtures'])
        print('Built', key, flush=True)
    key = 'battle-uncertain-opponent-lineup'
    for variant, starter, roster in [(None, 177, [151, 149, 1, 20, 10, 28]), ('variant-b', 153, [151, 149, 1, 22, 20, 154]), ('variant-c', 176, [151, 149, 1, 10, 22, 180])]:
        destination = root / key if variant is None else root / key / variant
        if (destination / 'scenario.json').exists():
            continue
        e, prov = load_source(rom, archive / 'event-786.state')
        team = [mon('JOLTEON', 55, [85, 86, 24, 42]), mon('LAPRAS', 55, [57, 58, 109, 34]), mon('SNORLAX', 55, [34, 89, 156, 133])]
        set_party(e, strategy, team)
        set_bag(e, [(18, 2), (16, 1)])
        e.memory[W_RIVAL_STARTER] = starter
        trace = []
        enter(e, trace)
        assert list(e.memory[55453:55459]) == roster
        prov.update(rival_starter=starter, native_enemy_party=roster, setup_commands=trace, offline_party=team, offline_bag=[(18, 2), (16, 1)])
        export(key, e, prov, None if variant is None else destination)
        e.close()
    key = 'battle-ineffective-attack-adaptation'
    if not (root / key / 'scenario.json').exists():
        for offset in range(60):
            e, prov = load_source(rom, root / 'battle-underleveled-status-setup/initial.state')
            if offset:
                e.tick(offset)
            machine = ChooseMove(0, version='red')
            trace = []
            for _ in range(1000):
                result = machine.step(e.memory, ui_state(e.memory))
                if isinstance(result, Done):
                    break
                trace.append(command(e, result))
            if ui_state(e.memory)['kind'] == 'battle_menu' and e.memory[53225] == 0 and (e.memory[53293] == 19):
                prov.update(prefix_offset_frames=offset, prefix_commands=trace, prefix_outcome=result.outcome)
                export(key, e, prov)
                e.close()
                break
            e.close()
        else:
            raise ValueError('Could not capture a native missed Hypnosis')
    key = 'battle-wild-basics'
    if not (root / key / 'scenario.json').exists():
        for offset in range(40):
            e, prov = load_source(rom, archive / 'event-12.state', 90)
            set_party(e, strategy, [mon('SQUIRTLE', 5, [33, 39])])
            set_bag(e, [(20, 1)])
            if offset:
                e.tick(offset)
            trace = []
            for step in range(140):
                trace.append(command(e, 'up' if step % 64 < 32 else 'down'))
                if e.memory[W_IS_IN_BATTLE]:
                    enter(e, trace)
                    break
            if e.memory[W_ENEMY_SPECIES2] == 165 and e.memory[W_ENEMY_LEVEL] == 3 and (ui_state(e.memory)['kind'] == 'battle_menu'):
                prov.update(offset=offset, setup_commands=trace, offline_party=[mon('SQUIRTLE', 5, [33, 39])], offline_bag=[(20, 1)])
                export(key, e, prov)
                e.close()
                break
            e.close()
        else:
            raise ValueError('No natural Rattata level3 found')
    key = 'operations-battle-switch'
    if not (root / key / 'scenario.json').exists():
        folder = private_root / 'data/red-ability-v4/fixtures/viridian-forest'
        e, prov = load_source(rom, folder / 'initial.state')
        commands = []
        for line in (folder / 'reference/actions.jsonl').read_text().splitlines():
            row = json.loads(line)
            a = row['action']
            before = e.save()
            command(e, a['button'], a['hold_frames'], a['release_frames'])
            commands.append(a)
            if e.memory[W_IS_IN_BATTLE] == 2 and e.memory[W_TRAINER_CLASS] == 2:
                e.load(before)
                team = [mon('CHARMANDER', 15, [10, 45, 52, 43], hp=30, max_hp=39), PIDGEY, PIKA]
                set_party(e, strategy, team)
                set_bag(e, [])
                command(e, a['button'], a['hold_frames'], a['release_frames'])
                for _ in range(100):
                    if ui_state(e.memory)['kind'] == 'battle_menu':
                        break
                    command(e, 'a')
                print('trainer', e.memory[W_ENEMY_SPECIES2], e.memory[W_ENEMY_LEVEL], flush=True)
                if e.memory[W_ENEMY_SPECIES2] != 112 or e.memory[W_ENEMY_LEVEL] != 7:
                    raise ValueError('Wrong native Bug Catcher')
                prov.update(offline_team=team, prefix_commands=commands, setup_writes='Own party and bag before trainer battle.')
                export(key, e, prov)
                break
        else:
            raise ValueError('No native Bug Catcher encountered')
        e.close()
    key = 'battle-heal-switch-attack-tradeoff'
    if not (root / key / 'scenario.json').exists():
        source = private_root / 'data/decision-v1-sources-v2/bruno'
        e, prov = load_source(rom, source / 'initial.state')
        team = [mon('KADABRA', 50, [94, 105, 50, 134]), mon('POLIWRATH', 50, [57, 95, 133, 156]), mon('PIDGEOT', 50, [17, 19, 98, 28])]
        set_party(e, strategy, team)
        set_bag(e, [(18, 1), (19, 1)])
        trace = []
        for a in read(source / 'entry-commands.json'):
            trace.append(command(e, a['button'], a['hold_frames'], a['release_frames']))
        enter(e, trace)
        for _ in range(30):
            if e.memory[W_ENEMY_SPECIES2] == 126:
                break
            if ui_state(e.memory)['kind'] == 'battle_menu':
                machine = ChooseMove(0, version='red')
                for _ in range(1000):
                    r = machine.step(e.memory, ui_state(e.memory))
                    if isinstance(r, Done):
                        break
                    trace.append(command(e, r))
            else:
                enter(e, trace)
        else:
            raise ValueError('Did not reach Machamp')
        enter(e, trace)
        assert e.memory[W_ENEMY_SPECIES2] == 126 and e.memory[W_ENEMY_LEVEL] == 58
        maximum = int.from_bytes(bytes(e.memory[W_PARTY_MONS + 34:W_PARTY_MONS + 36]), 'big')
        hp = int(maximum * 0.35)
        for base in (W_PARTY_MONS + 1, 53269):
            e.memory[base] = hp >> 8
            e.memory[base + 1] = hp & 255
        trace.append(command(e, 'a'))
        trace.append(command(e, 'b'))
        prov.update(setup_commands=trace, offline_team=team, midbattle_own_hp=hp, setup_writes='Own team before battle, then own active and party HP set to 35percent after native Machamp sendout.')
        export(key, e, prov)
        e.close()
if __name__ == '__main__':
    main()
