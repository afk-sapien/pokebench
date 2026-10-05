import argparse
import json
import os
from pathlib import Path
import sys
import time

from pokeagent_bench.core import core_provenance, digest, encoded, write_json
from pokeagent_bench.session import load_engine


class ReadOnlyMemory:
    def __init__(self, memory):
        self._memory = memory

    def __getitem__(self, key):
        return self._memory[key]


def main():
    parser = argparse.ArgumentParser(description='Use PokeSim only for offline controller-driven checkpoint curation')
    parser.add_argument('--pokesim', type=Path, required=True)
    parser.add_argument('--rom', type=Path, required=True)
    parser.add_argument('--scenario', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--story-only', action='store_true', help='Defer optional collection projects during curation')
    parser.add_argument('--max-frames', type=int, default=1000000)
    parser.add_argument('--max-seconds', type=int, default=600)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(args.pokesim))
    os.environ['GAME_DATA_DIR'] = str(args.pokesim / 'data/game-data')
    from pokesim.policies.strategic import StrategicPolicy
    from pokesim.policies.base import PolicyContext
    from pokesim.ram import read_snapshot, TRAINER_NAMES
    from pokesim.strategy_data import MAPS
    from pokesim.screen import Screen
    engine, source = load_engine(args.rom, args.scenario)
    memory = ReadOnlyMemory(engine.memory)
    policy = StrategicPolicy(7)
    if args.story_only:
        policy.collection.cooldown = args.max_frames + 1
    started = time.monotonic()
    frame = index = 0
    captures = []
    provenance = {str(p.relative_to(args.pokesim)): digest(p.read_bytes())
                  for p in sorted((args.pokesim / 'pokesim').rglob('*.py'))}
    write_json(args.output/'source.json', {'source_scenario': source, 'policy':'StrategicPolicy', 'seed':7, 'story_only':args.story_only,
               'pokesim_source_sha256': digest(encoded(provenance)), 'controller_only':True, 'core':core_provenance(),
               'max_frames':args.max_frames, 'max_seconds':args.max_seconds})

    def capture(name):
        destination = args.output / name
        destination.mkdir()
        state, preview = engine.save(), engine.screenshot()
        (destination/'initial.state').write_bytes(state)
        (destination/'preview.png').write_bytes(preview)
        manifest = {key: source[key] for key in ('format','game','rom_sha256','pyboy_version','core')}
        manifest.update(core=core_provenance(), name=name, objective={'kind':'milestone','target':'badge:boulder',
                       'description':'Defeat Brock and earn the Boulder Badge.'},
                       state_sha256=digest(state), preview_sha256=digest(preview), setup_wait_frames=0,
                       scenario_protocol='battle-v015',curation='pokesim-policy-unverified',
                       source_state_sha256=source['state_sha256'], source_prefix_actions=index,
                       source_prefix_frames=frame, pokesim_source_sha256=digest(encoded(provenance)))
        write_json(destination/'scenario.json',manifest)
        captures.append(name)
        print(json.dumps({'capture': name, 'frame':frame}),flush=True)

    try:
        with (args.output/'actions.jsonl').open('w') as log:
            while frame < args.max_frames and time.monotonic()-started < args.max_seconds:
                snapshot = read_snapshot(memory,frame)
                if snapshot.map == MAPS['PEWTER_GYM'] and not snapshot.badges & 1:
                    if 'brock-entrance-v015' not in captures and not snapshot.in_battle:
                        capture('brock-entrance-v015')
                    if (snapshot.in_battle == 2 and TRAINER_NAMES.get(snapshot.trainer_class,'').lower() == 'brock'
                            and Screen(memory).battle_menu):
                        capture('brock-battle-v015')
                        break
                actions = policy.step(PolicyContext(snapshot,0,time.monotonic()-started,memory))
                if not actions:
                    raise ValueError('PokeSim returned no controller actions')
                for action in actions:
                    if action.button:
                        engine.press(action.button)
                    if action.hold:
                        engine.tick(action.hold)
                    if action.button:
                        engine.release(action.button)
                    if action.gap:
                        engine.tick(action.gap)
                    frame += action.hold + action.gap
                    index += 1
                    log.write(json.dumps({'index':index,'frame':frame,'button':action.button,
                                         'hold_frames':action.hold,'release_frames':action.gap})+'\n')
                if index % 500 == 0:
                    print(json.dumps({'actions':index,'frame':frame,'map':snapshot.map_name,
                                      'party':[[m.name,m.level] for m in snapshot.party],
                                      'objective':policy.details().get('objective')}),flush=True)
    finally:
        (args.output/'final.state').write_bytes(engine.save())
        (args.output/'latest.png').write_bytes(engine.screenshot())
        write_json(args.output/'result.json',{'captures':captures,'frames':frame,'actions':index,
                   'seconds':time.monotonic()-started,'completed':'brock-battle-v015' in captures})
        engine.close()


if __name__ == '__main__':
    main()
