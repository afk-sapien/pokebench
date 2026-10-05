"""Record and replay an offline PokeSim reference from a benchmark checkpoint."""
import argparse
import os
from pathlib import Path
import sys

from pokeagent_bench.core import Limits, digest, encoded, write_json
from pokeagent_bench.session import Session, load_engine, replay
from prepare_pokesim_gym import ReadOnlyMemory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pokesim', type=Path, required=True)
    parser.add_argument('--rom', type=Path, required=True)
    parser.add_argument('--scenario', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--max-actions', type=int, default=2000)
    parser.add_argument('--max-frames', type=int, default=120000)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Refusing to overwrite a reference')
    sys.path.insert(0, str(args.pokesim))
    os.environ['GAME_DATA_DIR'] = str(args.pokesim/'data/game-data')
    from pokesim.policies.strategic import StrategicPolicy
    from pokesim.policies.base import PolicyContext
    from pokesim.ram import read_snapshot
    engine, manifest = load_engine(args.rom, args.scenario)
    session = Session(engine, args.output, manifest, track='visual', goal='challenge',
                      limits=Limits(max_actions=args.max_actions, max_frames=args.max_frames,
                                    max_action_frames=600))
    policy = StrategicPolicy(7)
    policy.collection.cooldown = args.max_frames + 1
    memory = ReadOnlyMemory(engine.memory)
    try:
        while not session.reason:
            snapshot = read_snapshot(memory, session.frame)
            commands = policy.step(PolicyContext(snapshot, 0, session.elapsed(), memory))
            if not commands or not any(command.hold + command.gap for command in commands):
                raise ValueError('Reference policy returned no advancing commands')
            for command in commands:
                if command.hold + command.gap == 0:
                    if command.button is not None:
                        raise ValueError('Zero-duration button command is unsupported')
                    continue
                if command.button is None:
                    session.wait(str(session.actions), command.hold + command.gap)
                else:
                    session.act(str(session.actions), command.button, command.hold, command.gap)
                if session.reason:
                    break
    finally:
        session.close()
    if session.reason != 'completed':
        raise ValueError(f'Reference did not achieve the objective: {session.reason}')
    proof = replay(args.rom, args.output)
    write_json(args.output/'verification.json', proof)
    manifest.update(curation='pokesim-policy-reference-verified', reference=proof)
    manifest.pop('definition_sha256', None)
    manifest['definition_sha256'] = digest(encoded(manifest))
    write_json(args.scenario/'scenario.json', manifest)
    print(proof)


if __name__ == '__main__':
    main()
