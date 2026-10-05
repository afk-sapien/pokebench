"""Extract unbeaten Gym Leader battles using PokeSim controller inputs only."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys
import time

from pokesim_core.gen1 import W_CUR_MAP, W_IS_IN_BATTLE, W_TRAINER_CLASS
from pokeagent_bench.core import digest, encoded, write_json
from pokeagent_bench.game import RedEngine
from pokeagent_bench.gameplay import ui_state
from pokeagent_bench.suite import GYM_SPECS, GYM_TASKS, check_start, read, reference
from prepare_basic_fixtures import advance, save_fixture
from prepare_pokesim_gym import ReadOnlyMemory

# These archived map-entry states precede each leader's first defeat.
EVENTS = {'surge': 240, 'erika': 368, 'koga': 527, 'sabrina': 591, 'blaine': 670, 'giovanni': 687}


def curate(rom, pokesim, archive, output, key):
    sys.path.insert(0, str(pokesim))
    os.environ['GAME_DATA_DIR'] = str(pokesim/'data/game-data')
    from pokesim.policies.strategic import StrategicPolicy
    from pokesim.policies.base import PolicyContext
    from pokesim.ram import read_snapshot
    source = archive/'states'/f'event-{EVENTS[key]}.state'
    raw = source.read_bytes()
    state = gzip.decompress(raw) if raw[:2] == b'\x1f\x8b' else raw
    engine = RedEngine(rom, state)
    template = read(Path('data/red-basic-v1-core014/fixtures/brock/scenario.json'))
    if digest(rom.read_bytes()) != template['rom_sha256']:
        raise ValueError('Curation ROM does not match the registered Red ROM')
    task = next(t for t in GYM_TASKS if t['id'] == key)
    name, badge, trainer, map_id, bit = GYM_SPECS[key]
    policy = StrategicPolicy(7)
    policy.collection.cooldown = 5_000_000
    memory = ReadOnlyMemory(engine.memory)
    provenance = {'source': str(source), 'source_sha256': digest(raw),
                  'decompressed_sha256': digest(state), 'rom_sha1': hashlib.sha1(rom.read_bytes()).hexdigest(),
                  'controller_only': True, 'extractor_sha256': digest(Path(__file__).read_bytes()),
                  'policy_sha256': digest(encoded({str(p.relative_to(pokesim)): digest(p.read_bytes())
                                       for p in sorted((pokesim/'pokesim').rglob('*.py'))}))}
    commands = []
    captured = None
    frame = 0
    started = time.monotonic()
    trace = output/f'{key}-curation.jsonl'
    try:
        with trace.open('x') as log:
            for index in range(40000):
                if frame > 2_000_000 or time.monotonic()-started > 600:
                    raise ValueError(f'{key} exceeded offline curation budget')
                progress = engine.evidence()
                if progress['badges'] & (1 << bit):
                    if captured is None:
                        raise ValueError('Badge was earned without capturing its battle')
                    command = {'button': None, 'hold_frames': 120, 'release_frames': 0}
                    advance(engine, command)
                    commands.append(command)
                    log.write(json.dumps(command)+'\n')
                    break
                if (captured is None and engine.memory[W_IS_IN_BATTLE] == 2
                        and engine.memory[W_TRAINER_CLASS] == trainer and engine.memory[W_CUR_MAP] == map_id
                        and ui_state(engine.memory)['kind'] == 'battle_menu'):
                    check_start(task, engine)
                    save_fixture(engine, template, output/key,
                                 {**task['objective'], 'description': f'Defeat {name} and earn the {badge.title()} Badge using the current party and supplies. You start at the battle menu. Do not nickname any Pokemon.'},
                                 {**provenance, 'prefix_actions': len(commands), 'prefix_frames': frame})
                    write_json(output/key/'starting-team.json', engine.structured())
                    captured = len(commands)
                    print('Captured', key, frame, flush=True)
                snapshot = read_snapshot(memory, frame)
                actions = policy.step(PolicyContext(snapshot, 0, time.monotonic()-started, memory))
                if not actions:
                    raise ValueError('Policy returned no controller inputs')
                for action in actions:
                    if action.hold+action.gap == 0:
                        continue
                    command = {'button': action.button, 'hold_frames': action.hold, 'release_frames': action.gap}
                    advance(engine, command)
                    commands.append(command)
                    frame += action.hold+action.gap
                    log.write(json.dumps(command)+'\n')
                if index % 1000 == 0:
                    print(key, frame, snapshot.map_name, flush=True)
            else:
                raise ValueError('Curation action limit reached')
    finally:
        engine.close()
    if captured is None:
        raise ValueError('Missing capture')
    proof = reference(rom, output/key, commands[captured:], output/key/'reference')
    write_json(output/key/'curation-proof.json', {**provenance, 'trace_sha256': digest(trace.read_bytes()), 'reference': proof})
    print('Verified', key, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom', type=Path, required=True)
    parser.add_argument('--pokesim', type=Path, required=True)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--keys', nargs='+', default=list(EVENTS))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    for key in args.keys:
        curate(args.rom, args.pokesim, args.archive, args.output, key)


if __name__ == '__main__':
    main()
