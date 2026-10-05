"""Build healing and healthy Brock fixtures using recorded or policy controller inputs."""
import argparse
import json
import os
from pathlib import Path
import sys
import time

from pokeagent_bench.core import digest, encoded, write_json, core_provenance
from pokeagent_bench.session import load_engine
from pokeagent_bench.suite import reference
from pokesim_core.gen1 import read_party, W_CUR_MAP, W_IS_IN_BATTLE


def save_fixture(engine, source, destination, objective, provenance):
    destination.mkdir(parents=True, exist_ok=False)
    state, screen = engine.save(), engine.screenshot()
    (destination/'initial.state').write_bytes(state)
    (destination/'preview.png').write_bytes(screen)
    manifest = {k:source[k] for k in ('format','game','rom_sha256','pyboy_version')}
    manifest.update(core=core_provenance(), name=destination.name, objective=objective,
                    state_sha256=digest(state), preview_sha256=digest(screen), setup_wait_frames=0,
                    curation='controller-only-reference-pending', provenance=provenance,
                    builder_sha256=digest(Path(__file__).read_bytes()))
    write_json(destination/'scenario.json', manifest)
    return manifest


def advance(engine, command):
    button, hold, gap = command['button'], command['hold_frames'], command['release_frames']
    if button:
        engine.press(button)
    if hold:
        engine.tick(hold)
    if button:
        engine.release(button)
    if gap:
        engine.tick(gap)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom', type=Path, required=True)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--pokesim', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args=parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    source=args.root/'scenarios/wild-battle-v015'
    trace=args.root/'data/pokesim-gym-v015-story/actions.jsonl'
    commands=[json.loads(line) for line in trace.read_text().splitlines()]
    engine, manifest=load_engine(args.rom, source)
    try:
        # Last outdoor boundary before the recorded Viridian Center visit.
        for command in commands[:469]:
            advance(engine, command)
        assert engine.memory[W_CUR_MAP] == 1 and engine.memory[W_IS_IN_BATTLE] == 0
        assert any(mon['hp'] < mon['max_hp'] for mon in read_party(engine.memory))
        heal=args.output/'heal'
        save_fixture(engine, manifest, heal,
                     {'kind':'heal','map_id':41, 'description':
                      'Visit the nearby Viridian Pokemon Center and restore every current party member to full HP with no status conditions. Keep the same Pokemon and do not black out.'},
                     {'source_state':manifest['state_sha256'], 'trace_sha256':digest(trace.read_bytes()),
                      'prefix_actions':469, 'controller_only':True})
    finally:
        engine.close()
    suffix=[{key:c[key] for key in ('button','hold_frames','release_frames')} for c in commands[469:528]]
    proof=reference(args.rom, heal, suffix, heal/'reference')
    print('Healing reference', proof, flush=True)

    sys.path.insert(0, str(args.pokesim))
    os.environ['GAME_DATA_DIR']=str(args.pokesim/'data/game-data')
    from pokesim.policies.strategic import StrategicPolicy
    from pokesim.policies.base import PolicyContext
    from pokesim.ram import read_snapshot, TRAINER_NAMES
    from prepare_pokesim_gym import ReadOnlyMemory
    policy_hash=digest(encoded({str(p.relative_to(args.pokesim)):digest(p.read_bytes())
                               for p in sorted((args.pokesim/'pokesim').rglob('*.py'))}))
    source=args.root/'scenarios/brock-entrance-v015'
    engine, manifest=load_engine(args.rom, source)
    memory=ReadOnlyMemory(engine.memory)
    policy=StrategicPolicy(7)
    policy.collection.cooldown=10_000_000
    started=time.monotonic()
    frame=0
    captured=False
    tail=[]
    path=args.output/'brock'
    try:
        with (args.output/'brock-curation.jsonl').open('w') as log:
            for index in range(12000):
                if frame > 500000 or time.monotonic()-started > 300:
                    raise ValueError('Healthy Brock fixture exceeded offline construction budget')
                snapshot=read_snapshot(memory, frame)
                healthy=bool(snapshot.party) and all(p.hp == p.max_hp and not p.status for p in snapshot.party)
                brock=(snapshot.in_battle == 2 and TRAINER_NAMES.get(snapshot.trainer_class,'').lower() == 'brock')
                if not captured and brock and healthy:
                    save_fixture(engine, manifest, path,
                        {'kind':'milestone','target':'badge:boulder','description':'Defeat Brock and earn the Boulder Badge. You start in battle with a healthy party. Keep default Pokemon names.'},
                        {'source_state':manifest['state_sha256'], 'controller_only':True, 'prefix_frames':frame, 'policy_sha256':policy_hash})
                    captured=True
                    print('Captured healthy Brock battle', frame, flush=True)
                if not captured and not snapshot.in_battle and not healthy:
                    policy.heal_latch=True
                if snapshot.badges & 1:
                    if not captured:
                        raise ValueError('Brock was defeated before a healthy fixture was captured')
                    break
                actions=policy.step(PolicyContext(snapshot,0,time.monotonic()-started,memory))
                if not actions:
                    raise ValueError('Curation returned no actions')
                for action in actions:
                    command={'button':action.button,'hold_frames':action.hold,'release_frames':action.gap}
                    if action.hold+action.gap == 0:
                        continue
                    advance(engine, command)
                    frame+=action.hold+action.gap
                    log.write(json.dumps(command)+'\n')
                    if captured:
                        tail.append(command)
                if index % 500 == 0:
                    print(index,frame,snapshot.map_name,policy.details().get('objective'),flush=True)
            else:
                raise ValueError('Curation action budget exhausted')
        if not captured:
            raise ValueError('No healthy Brock battle reached')
    finally:
        engine.close()
    proof=reference(args.rom, path, tail, path/'reference')
    print('Healthy Brock reference',proof,flush=True)


if __name__ == '__main__':
    main()
