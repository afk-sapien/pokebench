"""Curate shopping, navigation, fossil and gym tasks through controller input only."""
import argparse
import json
import os
from pathlib import Path
import sys
import time

from pokesim_core.gen1 import W_CUR_MAP, W_IS_IN_BATTLE, W_TRAINER_CLASS, W_Y
from pokeagent_bench.core import digest, encoded, write_json
from pokeagent_bench.game import RedEngine
from pokeagent_bench.gameplay import ui_state
from pokeagent_bench.session import load_engine
from pokeagent_bench.suite import ADVENTURE_TASKS, check_start, read, reference
from prepare_basic_fixtures import advance, save_fixture
from prepare_pokesim_gym import ReadOnlyMemory

DESCRIPTIONS = {
    'buy-pokeballs': 'Visit the Viridian Poke Mart and buy at least ten Poke Balls with your money. Finish shopping and close the menus while still inside the Mart. Do not black out.',
    'viridian-forest': 'Cross Viridian Forest and reach Pewter City. You start at the southern end of the forest. Handle encounters and supplies as needed. Do not black out. Keep default Pokemon names.',
    'mt-moon': 'Travel through Mt. Moon and reach Cerulean City. You start inside the western cave entrance. Do not black out. Keep default Pokemon names.',
    'fossil': 'Defeat the Super Nerd and claim either fossil. Finish the interaction with the fossil in your bag. Do not black out. Keep default Pokemon names.',
    'misty': 'Defeat Misty and earn the Cascade Badge using this party and these supplies. Keep default Pokemon names.',
}


def capture(engine, manifest, output, key, provenance):
    task = next(t for t in ADVENTURE_TASKS if t['id'] == key)
    check_start(task, engine)
    save_fixture(engine, manifest, output/key, {**task['objective'], 'description': DESCRIPTIONS[key]},
                 {**provenance, 'extractor_sha256': digest(Path(__file__).read_bytes()), 'controller_only': True})


def early(root, rom, output):
    source = root/'scenarios/wild-battle-v015'
    trace = root/'data/pokesim-gym-v015-story/actions.jsonl'
    original = read(root/'data/pokesim-gym-v015-story/source.json')['source_scenario']
    engine, manifest = load_engine(rom, source)
    assert manifest['state_sha256'] == original['state_sha256']
    rows = [json.loads(line) for line in trace.read_text().splitlines()]
    commands = [{k:r[k] for k in ('button','hold_frames','release_frames')} for r in rows]
    offsets = {}
    frame = 0
    last_map = None
    map_age = 0
    try:
        for index, command in enumerate(commands):
            advance(engine, command)
            frame += command['hold_frames'] + command['release_frames']
            assert frame == rows[index]['frame']
            where = engine.memory[W_CUR_MAP]
            map_age = map_age + command['hold_frames'] + command['release_frames'] if where == last_map else 0
            last_map = where
            facts = engine.challenge_evidence({'kind': 'capture'})
            settled = map_age >= 120 and ui_state(engine.memory)['kind'] == 'overworld' and facts['battle'] == 0
            key = None
            if settled and where == 1 and facts['parcel_delivered'] and facts['balls'] == 0:
                key = 'buy-pokeballs'
            if settled and where == 51:
                key = 'viridian-forest'
            if key and key not in offsets:
                capture(engine, manifest, output, key, {'source_state_sha256': manifest['state_sha256'],
                        'trace_sha256': digest(trace.read_bytes()), 'prefix_actions': index+1, 'prefix_frames': frame})
                offsets[key] = index+1
                print('Captured', key, frame, flush=True)
            if len(offsets) == 2:
                break
    finally:
        engine.close()
    assert len(offsets) == 2
    for key, offset in offsets.items():
        reference(rom, output/key, commands[offset:], output/key/'reference')
        print('Verified', key, flush=True)


def later(root, rom, pokesim, output, reuse=None):
    source = root/'data/red-basic-v1-core014/fixtures/brock'
    state = (source/'reference/final.state').read_bytes()
    manifest = read(source/'scenario.json')
    assert read(source/'reference/result.json')['completed']
    assert digest(rom.read_bytes()) == manifest['rom_sha256']
    (output/'extension-start.state').write_bytes(state)
    trace = output/'extension-actions.jsonl'
    if reuse:
        assert digest((reuse/'extension-start.state').read_bytes()) == digest(state)
        trace.write_bytes((reuse/'extension-actions.jsonl').read_bytes())
        policy_hash = read(reuse/'misty/scenario.json')['provenance']['policy_sha256']
    else:
        sys.path.insert(0, str(pokesim))
        os.environ['GAME_DATA_DIR'] = str(pokesim/'data/game-data')
        from pokesim.policies.strategic import StrategicPolicy
        from pokesim.policies.base import PolicyContext
        from pokesim.ram import read_snapshot
        policy_hash = digest(encoded({str(p.relative_to(pokesim)): digest(p.read_bytes())
                                     for p in sorted((pokesim/'pokesim').rglob('*.py'))}))
        engine = RedEngine(rom, state)
        policy = StrategicPolicy(7)
        policy.collection.cooldown = 2_000_000
        memory = ReadOnlyMemory(engine.memory)
        frame = 0
        started = time.monotonic()
        try:
            with trace.open('x') as log:
                for index in range(50000):
                    if frame >= 1_500_000 or time.monotonic()-started > 600:
                        raise ValueError('Offline curation budget exhausted')
                    if engine.evidence()['badges'] & 2:
                        command = {'button': None, 'hold_frames': 60, 'release_frames': 0}
                        advance(engine, command)
                        log.write(json.dumps(command)+'\n')
                        break
                    snapshot = read_snapshot(memory, frame)
                    actions = policy.step(PolicyContext(snapshot, 0, time.monotonic()-started, memory))
                    if not actions:
                        raise ValueError('Offline policy returned no controller actions')
                    for action in actions:
                        if action.hold+action.gap == 0:
                            continue
                        command = {'button': action.button, 'hold_frames': action.hold, 'release_frames': action.gap}
                        advance(engine, command)
                        frame += action.hold+action.gap
                        log.write(json.dumps(command)+'\n')
                    if index % 2000 == 0:
                        print('Curation', frame, snapshot.map_name, flush=True)
                else:
                    raise ValueError('Offline curation action budget exhausted')
        finally:
            engine.close()
    commands = [json.loads(line) for line in trace.read_text().splitlines()]
    engine = RedEngine(rom, state)
    candidates = {}
    frame = map_age = 0
    last_map = None
    entrance_saved = reached_city = False
    try:
        for index, command in enumerate(commands):
            advance(engine, command)
            duration = command['hold_frames'] + command['release_frames']
            frame += duration
            where = engine.memory[W_CUR_MAP]
            map_age = map_age + duration if where == last_map else 0
            if where != last_map:
                entrance_saved = False
            last_map = where
            battle = engine.memory[W_IS_IN_BATTLE]
            kind = ui_state(engine.memory)['kind']
            if where == 3 and map_age >= 120:
                reached_city = True
            key = None
            if (not reached_city and not entrance_saved and where == 59 and map_age >= 120
                    and engine.memory[W_Y] >= 30 and battle == 0 and kind == 'overworld'):
                key = 'mt-moon'
                entrance_saved = True
            if where == 61 and battle == 2 and engine.memory[W_TRAINER_CLASS] == 8 and kind == 'battle_menu':
                key = 'fossil' if 'fossil' not in candidates else None
            if where == 65 and battle == 2 and engine.memory[W_TRAINER_CLASS] == 35 and kind == 'battle_menu':
                key = 'misty' if 'misty' not in candidates else None
            if key:
                candidates[key] = (engine.save(), engine.screenshot(), index+1, frame)
    finally:
        engine.close()
    if set(candidates) != {'mt-moon','fossil','misty'}:
        raise ValueError(f'Missing checkpoints: {list(candidates)}')
    for key, (saved, screen, offset, frame) in candidates.items():
        engine = RedEngine(rom, saved)
        engine.initial_screen = screen
        try:
            capture(engine, manifest, output, key, {'source_state_sha256': digest(state),
                    'source_reference': str(source/'reference'), 'policy_sha256': policy_hash,
                    'trace_sha256': digest(trace.read_bytes()), 'prefix_actions': offset, 'prefix_frames': frame,
                    'selection': 'last settled western cave entry before first Cerulean arrival' if key=='mt-moon' else 'first battle menu'})
        finally:
            engine.close()
        reference(rom, output/key, commands[offset:], output/key/'reference')
        print('Verified', key, frame, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--rom', type=Path, required=True)
    parser.add_argument('--pokesim', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--reuse-extension', type=Path)
    args = parser.parse_args()
    root, output = args.root.resolve(), args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    early(root, args.rom, output)
    later(root, args.rom, args.pokesim, output, args.reuse_extension)
    mapping = {t['id']: {'scenario': str(output/t['id']), 'reference': str(output/t['id']/'reference')}
               for t in ADVENTURE_TASKS}
    write_json(output/'bindings.json', mapping)
    original = root/'data/red-ability-v2'
    for key, fixture in read(original/'suite.json')['fixtures'].items():
        path = original/fixture['scenario']
        mapping[key] = {'scenario': str(path), 'reference': str(path/'reference')}
    write_json(output/'expanded-bindings.json', mapping)


if __name__ == '__main__':
    main()
