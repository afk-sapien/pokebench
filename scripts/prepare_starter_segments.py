"""Derive private starter checkpoints from a verified controller reference."""
import argparse
from copy import deepcopy
import json
from pathlib import Path

from pokeagent_bench.challenges import evidence
from pokeagent_bench.core import Limits, digest, encoded, write_json
from pokeagent_bench.session import Session, load_engine, replay


def advance(engine, row):
    command = row['action']
    button = command['button']
    if button:
        engine.press(button)
    for frame in range(row['executed_frames']):
        if button and frame == command['hold_frames']:
            engine.release(button)
        engine.tick()
    if button:
        engine.release(button)


def prepare_segments(rom, scenario, reference, output):
    verified = replay(rom, reference)
    if verified['score'] != 1:
        raise ValueError('Reference must complete the starter challenge')
    original = json.loads((scenario / 'scenario.json').read_text())
    reference_manifest = json.loads((reference / 'manifest.json').read_text())
    if reference_manifest['initial_sha256'] != original['state_sha256']:
        raise ValueError('Reference and source scenario must have the same initial state')
    if original['objective']['kind'] != 'opening' or original['objective']['target'] != 'starter':
        raise ValueError('Source must be a starter scenario')
    targets = {37: 'downstairs', 0: 'outside'}
    destinations = {map_id: output / f'starter-{name}-v014' for map_id, name in targets.items()}
    if any(path.exists() for path in destinations.values()):
        raise ValueError('Refusing to overwrite a segment checkpoint')
    rows = [json.loads(line) for line in (reference / 'actions.jsonl').read_text().splitlines()]
    engine, _ = load_engine(rom, scenario)
    captured = {}
    try:
        for index, row in enumerate(rows, 1):
            advance(engine, row)
            if digest(engine.screenshot()) != row['screenshot_sha256']:
                raise ValueError(f'Prefix screenshot diverged at action {index}')
            facts = evidence(engine, original['objective'])
            if facts != row['evidence']:
                raise ValueError(f'Prefix evidence diverged at action {index}')
            map_id = facts['map_id']
            if map_id not in targets or map_id in captured:
                continue
            if facts['challenge']['party_count'] or facts['story']['starter']:
                raise ValueError('Segment must begin before receiving a starter')
            path = destinations[map_id]
            path.mkdir(parents=True)
            state = engine.save()
            preview = engine.screenshot()
            (path / 'initial.state').write_bytes(state)
            (path / 'preview.png').write_bytes(preview)
            manifest = {key: deepcopy(original[key]) for key in ('format', 'game', 'rom_sha256', 'pyboy_version', 'core')}
            manifest.update(name=f'starter-{targets[map_id]}-v014', objective={
                'kind': 'opening', 'target': 'starter',
                'description': 'Obtain your first starter Pokemon from Professor Oak. Find your own way. Finish the acquisition dialogue and decline a nickname.'},
                state_sha256=digest(state), preview_sha256=digest(preview), setup_wait_frames=0,
                curation='reference-suffix-pending', scenario_protocol='starter-segments-v014',
                source_state_sha256=original['state_sha256'],
                source_reference_trace_head=verified['trace_head'], source_prefix_actions=index,
                source_prefix_frames=row['frame'], source_prefix_trace_head=row['hash'])
            write_json(path / 'scenario.json', manifest)
            captured[map_id] = (path, index)
            if len(captured) == len(targets):
                break
    finally:
        engine.close()
    if set(captured) != set(targets):
        raise ValueError('Reference does not contain both required starting locations')
    results = []
    for map_id, (path, prefix) in captured.items():
        restored, manifest = load_engine(rom, path)
        session = Session(restored, path / 'reference', manifest, track='visual', goal='challenge',
                          limits=Limits(max_action_frames=600, max_actions=1000))
        try:
            for index, row in enumerate(rows[prefix:], 1):
                session.act(str(index), **row['action'])
                if digest(restored.screenshot()) != row['screenshot_sha256']:
                    raise ValueError(f'Restored suffix diverged at action {index}')
                if session.reason:
                    break
            if session.reason != 'completed':
                raise ValueError('Restored checkpoint did not complete the reference suffix')
        finally:
            session.close()
        suffix = replay(rom, path / 'reference')
        manifest.update(curation='controller-reference-verified', reference=suffix)
        manifest['definition_sha256'] = digest(encoded(manifest))
        write_json(path / 'scenario.json', manifest)
        results.append({'name':manifest['name'], 'map_id':map_id, 'state_sha256':manifest['state_sha256'],
                        'preview_sha256':manifest['preview_sha256'], 'prefix_actions':prefix,
                        'reference':suffix, 'definition_sha256':manifest['definition_sha256']})
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom', type=Path, required=True)
    parser.add_argument('--scenario', type=Path, required=True)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare_segments(args.rom, args.scenario, args.reference, args.output), indent=2))


if __name__ == '__main__':
    main()
