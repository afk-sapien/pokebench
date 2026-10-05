"""Rebuild a private wild-battle fixture from recorded controller actions."""
import argparse
import json
from pathlib import Path

from pokeagent_bench.challenges import ChallengeEvaluator, evidence
from pokeagent_bench.core import Limits, action, core_provenance, digest, encoded, write_json
from pokeagent_bench.game import RedEngine
from pokeagent_bench.session import Session, load_engine, replay


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom', type=Path, required=True)
    parser.add_argument('--source-run', type=Path, required=True)
    parser.add_argument('--curation-actions', type=Path, required=True)
    parser.add_argument('--reference-run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Refusing to overwrite a checkpoint')
    source_replay = replay(args.rom, args.source_run)
    source = json.loads((args.source_run/'manifest.json').read_text())
    state = (args.source_run/'final.state').read_bytes()
    engine = RedEngine(args.rom, state)
    objective = {'kind': 'wild-battle',
                 'description': 'Win this wild Pokemon battle. Defeat the opponent without fleeing or catching it.'}
    try:
        for index, row in enumerate(json.loads(args.curation_actions.read_text()), 1):
            command = action(**{key:row[key] for key in ('button','hold_frames','release_frames')}, maximum=600)
            if command['button']:
                engine.press(command['button'])
            for frame in range(command['hold_frames']+command['release_frames']):
                if frame == command['hold_frames'] and command['button']:
                    engine.release(command['button'])
                engine.tick()
            if command['button']:
                engine.release(command['button'])
            if digest(engine.screenshot()) != row['screenshot_sha256']:
                raise ValueError(f'Curation screenshot differs at action {index}')
        ChallengeEvaluator(evidence(engine, objective), objective)
        args.output.mkdir(parents=True)
        saved, preview = engine.save(), engine.screenshot()
        (args.output/'initial.state').write_bytes(saved)
        (args.output/'preview.png').write_bytes(preview)
        manifest = {key: source['scenario'][key] for key in ('format','game','rom_sha256','pyboy_version')}
        manifest.update(name=args.output.name, core=core_provenance(), objective=objective,
                        scenario_protocol='battle-v015', setup_wait_frames=0, curation='pending',
                        source_state_sha256=digest(state), source_replay=source_replay,
                        curation_actions_sha256=digest(args.curation_actions.read_bytes()),
                        state_sha256=digest(saved), preview_sha256=digest(preview))
        write_json(args.output/'scenario.json', manifest)
    finally:
        engine.close()
    engine, manifest = load_engine(args.rom, args.output)
    session = Session(engine, args.output/'reference', manifest, track='visual', goal='challenge',
                      limits=Limits(max_action_frames=600, max_actions=1000))
    try:
        for index, line in enumerate((args.reference_run/'actions.jsonl').read_text().splitlines(), 1):
            row = json.loads(line)
            session.act(str(index), **row['action'])
            if session.reason:
                break
        if session.reason != 'completed':
            raise ValueError('Reference did not win the battle')
    finally:
        session.close()
    manifest.update(curation='controller-reference-verified', reference=replay(args.rom,args.output/'reference'))
    manifest['definition_sha256'] = digest(encoded(manifest))
    write_json(args.output/'scenario.json', manifest)
    print(json.dumps(manifest,indent=2))


if __name__ == '__main__':
    main()
