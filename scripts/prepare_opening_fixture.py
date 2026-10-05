"""Create a gameplay checkpoint and verify its controller reference without models."""
import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from pokeagent_bench.core import Limits, digest, write_json
from pokeagent_bench.game import RedEngine
from pokeagent_bench.session import Session, checkpoint, load_engine, replay


def prepare_fixture(rom, definition, output):
    data = json.loads(definition.read_text())
    with RedEngine(rom) as engine, TemporaryDirectory() as temporary:
        for command in data['setup_actions']:
            button = command['button']
            if button != 'wait':
                engine.press(button)
            engine.tick(command['hold_frames'])
            if button != 'wait':
                engine.release(button)
            if command['release_frames']:
                engine.tick(command['release_frames'])
        state = Path(temporary) / 'start.state'
        state.write_bytes(engine.save())
        checkpoint(rom, state, output, name=data['name'], objective=data['objective'])
    engine, manifest = load_engine(rom, output)
    manifest['definition_sha256'] = digest(definition.read_bytes())
    write_json(output / 'scenario.json', manifest)
    session = Session(engine, output / 'reference', manifest, goal='challenge',
                      limits=Limits(max_actions=1000, max_frames=100000, max_action_frames=600))
    try:
        for index, command in enumerate(data['reference_actions']):
            session.act(str(index), None if command['button'] == 'wait' else command['button'],
                        command['hold_frames'], command['release_frames'])
            if session.status()['state'] == 'finished':
                break
        if not session.status()['completed']:
            raise ValueError('The controller reference did not complete its objective')
    finally:
        session.close()
    manifest['reference'] = replay(rom, output / 'reference')
    manifest['curation'] = 'controller-reference-verified'
    write_json(output / 'scenario.json', manifest)
    return manifest['reference']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom', required=True, type=Path)
    parser.add_argument('--definition', default=Path('fixtures/opening-starter-v1.json'), type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(prepare_fixture(args.rom, args.definition, args.output), indent=2))
