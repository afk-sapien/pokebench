"""Curate two tiny private control tasks from the recorded Mansion checkpoint.

This script expects the source save at map 165, x=6, y=26 outside battle.
Only waits and controller buttons advance the source in an isolated emulator.
"""
import argparse
from pathlib import Path
from tempfile import TemporaryDirectory

from pokeagent_bench.core import Limits, digest, write_json
from pokeagent_bench.game import RedEngine
from pokeagent_bench.session import Session, checkpoint, load_engine, replay


def prepare_controls(rom, source, output):
    source_bytes = source.read_bytes()
    with RedEngine(rom, source_bytes) as engine:
        game = engine.structured()
        assert game['location'] == {'map_id': 165, 'map_name': '#165', 'x': 6, 'y': 26}
        assert game['battle']['kind'] == 'none'
        engine.tick(24)
        base = engine.save()
    objective = {'kind': 'location', 'map_id': 165, 'x': 7, 'y': 26,
                 'description': 'Reach tile x=7, y=26 on map 165. Close any open menu first.'}
    for name, menu in [('mansion-step-right-v1', False), ('mansion-close-menu-v1', True)]:
        with RedEngine(rom, base) as engine, TemporaryDirectory() as temporary:
            setup = [{'button': 'wait', 'hold_frames': 24, 'release_frames': 0}]
            if menu:
                for button in ('up', 'down', 'left', 'right', 'a', 'b', 'start', 'select'):
                    engine.release(button)
                engine.tick(120)
                setup.append({'release_all_buttons': True, 'wait_frames': 120})
                engine.press('start')
                engine.tick(8)
                engine.release('start')
                engine.tick(60)
                setup.append({'button': 'start', 'hold_frames': 8, 'release_frames': 60})
            state_path = Path(temporary) / 'input.state'
            state_path.write_bytes(engine.save())
            scenario = output / name
            manifest = checkpoint(rom, state_path, scenario, name=name, objective=objective)
        manifest['source_state_sha256'] = digest(source_bytes)
        manifest['setup_actions'] = setup
        write_json(scenario / 'scenario.json', manifest)
        engine, manifest = load_engine(rom, scenario)
        reference = scenario / 'reference'
        session = Session(engine, reference, manifest, goal='challenge', limits=Limits(max_actions=5))
        try:
            if menu:
                session.act('close-menu', 'b', 8, 16)
            session.act('step-right', 'right', 8, 16)
            assert session.status()['completed'], session.status()
        finally:
            session.close()
        verified = replay(rom, reference)
        assert verified['verified']
        manifest['curation'] = 'controller-reference-verified'
        manifest['reference'] = verified
        write_json(scenario / 'scenario.json', manifest)
        print(name, verified)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom', required=True, type=Path)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output', default=Path('scenarios'), type=Path)
    args = parser.parse_args()
    prepare_controls(args.rom, args.source, args.output)
