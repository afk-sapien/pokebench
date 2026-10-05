"""Curate new ability checkpoints from retained controller traces, without model calls."""
import argparse
import json
from pathlib import Path

from pokesim_core.gen1 import W_IS_IN_BATTLE, W_TRAINER_CLASS, read_party, read_bag

from pokeagent_bench.core import Limits, digest, encoded, write_json
from pokeagent_bench.game import RedEngine
from pokeagent_bench.gameplay import load_catalog, ui_state
from pokeagent_bench.gameplay_commands import execute
from pokeagent_bench.session import Session, replay
from pokeagent_bench.suite import SKILL_TASKS, check_start, reference, read
from prepare_basic_fixtures import advance, save_fixture


def elite_segments(root, rom, output):
    run = root / 'data/red-league-v1-core014/fixtures/league/reference'
    source = read(run / 'manifest.json')
    rows = [json.loads(line) for line in (run / 'actions.jsonl').read_text().splitlines()]
    engine = RedEngine(rom, (run / 'initial.state').read_bytes())
    assert digest((run / 'initial.state').read_bytes()) == source['initial_sha256']
    assert digest(rom.read_bytes()) == source['scenario']['rom_sha256']
    found = {}
    head = '0' * 64
    frame = 0
    try:
        for index, original in enumerate(rows):
            row = dict(original)
            claimed = row.pop('hash')
            assert row['previous_hash'] == head and digest(encoded(row)) == claimed
            assert row['before_frame'] == frame
            head = claimed
            command = dict(row['action'])
            hold = min(command['hold_frames'], row['executed_frames'])
            command.update(hold_frames=hold, release_frames=row['executed_frames'] - hold)
            advance(engine, command)
            frame += row['executed_frames']
            assert frame == row['frame']
            key = {46: 'agatha', 47: 'lance'}.get(engine.memory[W_TRAINER_CLASS])
            if (key and key not in found and engine.memory[W_IS_IN_BATTLE] == 2
                    and ui_state(engine.memory)['kind'] == 'battle_menu'):
                assert digest(engine.screenshot()) == row['screenshot_sha256']
                task = next(task for task in SKILL_TASKS if task['id'] == key)
                check_start(task, engine)
                save_fixture(engine, source['scenario'], output / key,
                    {**task['objective'], 'description': f'Defeat {key.title()} in this battle. Use the party and supplies provided. Do not nickname any Pokemon.'},
                    {'source_run': str(run), 'source_state_sha256': source['initial_sha256'],
                     'prefix_frames': frame, 'prefix_actions': index + 1,
                     'trace_head': head, 'controller_only': True})
                found[key] = index + 1
                print('Captured', key, 'at frame', frame, flush=True)
        assert set(found) == {'agatha', 'lance'}
    finally:
        engine.close()
    for key, offset in found.items():
        commands = []
        for row in rows[offset:]:
            command = dict(row['action'])
            hold = min(command['hold_frames'], row['executed_frames'])
            command.update(hold_frames=hold, release_frames=row['executed_frames'] - hold)
            commands.append(command)
        reference(rom, output / key, commands, output / key / 'reference')
        print('Verified', key, flush=True)


def item_recovery(root, rom, catalog, output):
    source = root / 'data/menu-v036-verified/fixtures'
    proof = read(source / 'sources.json')['decisions']['150']
    state = (source / 'decision-150.state').read_bytes()
    screen = (source / 'decision-150.png').read_bytes()
    assert digest(state) == proof['state_sha256']
    assert digest(screen) == proof['screenshot_sha256']
    original = read(root / 'data/league-v1-comparison-restart-01/batch/cell-0003/manifest.json')
    assert digest(rom.read_bytes()) == original['scenario']['rom_sha256']
    engine = RedEngine(rom, state)
    engine.initial_screen = screen
    target = output / 'item-recovery'
    task = SKILL_TASKS[0]
    scenario = save_fixture(engine, original['scenario'], target,
        {**task['objective'], 'description': 'Use your bag to restore every current party member to full HP and clear status conditions. Stay in this League room, keep the same Pokemon, and do not black out. PP restoration is not required.'},
        {'source_run': str(root / 'data/league-v1-comparison-restart-01/batch/cell-0003'),
         'source_runtime_sha256': original['source_sha256'], 'source_decision': 150,
         'source_state_sha256': digest(state), 'controller_only': True})
    session = Session(engine, target / 'reference', scenario, track='gameplay', goal='challenge',
                      limits=Limits(max_action_frames=600), gameplay_catalog=catalog,
                      agent={'provider': 'controller-reference', 'model': 'none'})
    try:
        for slot in range(len(read_party(engine.memory))):
            if session.reason:
                break
            mon = read_party(engine.memory)[slot]
            if mon['hp'] == 0:
                execute(session, f'revive-{slot}', {'command':'use_item','argument':f'Revive:{slot+1}','count':1})
            mon = read_party(engine.memory)[slot]
            if not session.reason and (mon['hp'] < mon['max_hp'] or mon['status']):
                item = 'Full Restore' if dict(read_bag(engine.memory)).get(16, 0) else 'Max Potion'
                execute(session, f'heal-{slot}', {'command':'use_item','argument':f'{item}:{slot+1}','count':1})
                if not session.reason:
                    execute(session, f'settle-{slot}', {'command':'wait','argument':'','count':120})
        for step in range(3):
            if session.reason or ui_state(engine.memory)['kind'] != 'menu':
                break
            execute(session, f'close-{step}', {'command':'press','argument':'b','count':1})
        if not session.reason:
            session.finish('reference_exhausted')
    finally:
        session.close()
    assert read(target / 'reference/result.json')['completed']
    assert replay(rom, target / 'reference')['verified']
    print('Verified item recovery', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--rom', type=Path, required=True)
    parser.add_argument('--game-data', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    elite_segments(args.root, args.rom, args.output)
    item_recovery(args.root, args.rom, load_catalog(args.game_data), args.output)
    mapping = {}
    for name in ('red-basic-v1-core014', 'red-league-v1-core014'):
        source = args.root / 'data' / name
        for key, fixture in read(source / 'suite.json')['fixtures'].items():
            path = (source / fixture['scenario']).resolve()
            mapping[key] = {'scenario': str(path), 'reference': str(path / 'reference')}
    for task in SKILL_TASKS:
        path = args.output / task['id']
        mapping[task['id']] = {'scenario': str(path), 'reference': str(path / 'reference')}
    write_json(args.output / 'bindings.json', mapping)
    print('All nine task bindings ready', flush=True)


if __name__ == '__main__':
    main()
