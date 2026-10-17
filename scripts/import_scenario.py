"""Copy a Gen 1 scenario into the current Core runtime without advancing gameplay."""
import argparse
import json
from pathlib import Path

from pokeagent_bench.core import core_provenance, digest, emulator_manifest, write_json
from pokeagent_bench.game import RedEngine
from pokeagent_bench.challenges import validate_objective


def import_scenario(rom, source, output):
    if output.exists():
        raise ValueError('Destination already exists. Original scenarios are never overwritten.')
    original = json.loads((source / 'scenario.json').read_text())
    raw = (source / 'initial.state').read_bytes()
    if original.get('game') != 'red' or original.get('format') != 1:
        raise ValueError('Only Gen 1 Red scenarios are supported')
    if digest(raw) != original['state_sha256'] or digest(rom.read_bytes()) != original['rom_sha256']:
        raise ValueError('Source state or ROM checksum mismatch')
    if 'objective' in original:
        validate_objective(original['objective'])
    preview = (source / 'preview.png').read_bytes()
    if original.get('preview_sha256') and digest(preview) != original['preview_sha256']:
        raise ValueError('Source preview checksum mismatch')
    with RedEngine(rom, raw) as engine:
        facts = engine.structured()
        snapshot = engine.save()
    with RedEngine(rom, snapshot) as restored:
        if restored.structured() != facts:
            raise ValueError('Imported state failed its save/load round trip')
    manifest = {key: value for key, value in original.items() if key not in ('emulator', 'pyboy_version', 'core')}
    manifest.update(**emulator_manifest(), core=core_provenance(),
                    runtime_import={'source_manifest_sha256': digest((source / 'scenario.json').read_bytes()),
                                    'source_emulator': original.get('emulator', {'backend': 'pyboy',
                                                                             'version': original.get('pyboy_version')}),
                                    'source_core': original.get('core'), 'frames_advanced': 0,
                                    'state_bytes_preserved': True, 'round_trip_verified': True})
    output.mkdir(parents=True)
    (output / 'initial.state').write_bytes(raw)
    (output / 'preview.png').write_bytes(preview)
    write_json(output / 'scenario.json', manifest)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    imported = import_scenario(args.rom, args.source, args.output)
    print(json.dumps({'output': str(args.output), 'emulator': imported['emulator'],
                      'import': imported['runtime_import']}))


if __name__ == '__main__':
    main()
