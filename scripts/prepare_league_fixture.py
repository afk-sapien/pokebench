"""Import an archived PokeSim League entry without changing the source save."""
import argparse
import gzip
import os
from pathlib import Path
import subprocess
import sys

from pokeagent_bench.core import digest, encoded, write_json
from pokeagent_bench.game import RedEngine
from pokeagent_bench.session import checkpoint
from pokeagent_bench.suite import HARD_LEAGUE_TASK, LEAGUE_TASK, check_start, read


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom', type=Path, required=True)
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--pokesim', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--hard', action='store_true', help='Register a difficult-team League fixture')
    args = parser.parse_args()
    task = HARD_LEAGUE_TASK if args.hard else LEAGUE_TASK
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    source = args.state.read_bytes()
    raw = gzip.decompress(source) if source[:2] == b'\x1f\x8b' else source
    engine = RedEngine(args.rom, raw)
    try:
        # Archived map-entry events can precede the fade and arrival animation.
        engine.tick(120)
        check_start(task, engine)
        (output/'settled.state').write_bytes(engine.save())
        write_json(output/'source.json', {
            'source': str(args.state.resolve()), 'source_sha256': digest(source),
            'decompressed_sha256': digest(raw), 'setup_wait_frames': 120,
            'starting_party': engine.structured(), 'evidence': engine.evidence()})
    finally:
        engine.close()
    checkpoint(args.rom, output/'settled.state', output/'scenario',
               name='league-hard-v1' if args.hard else 'league-first-championship-v1', objective={
                   **task['objective'],
                   'description': 'Defeat Lorelei, Bruno, Agatha, Lance, and the Champion, then complete '
                                  'the Hall of Fame registration. Use the party and supplies in this '
                                  'save. Do not nickname any Pokemon.'})
    script = Path(__file__).with_name('verify_pokesim_checkpoint.py')
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]/'src'))
    subprocess.run([sys.executable, str(script), '--rom', str(args.rom.resolve()),
                    '--pokesim', str(args.pokesim.resolve()), '--scenario', str(output/'scenario'),
                    '--output', str(output/'reference'), '--max-actions', '15000',
                    '--max-frames', '1800000'], check=True, env=env)
    manifest = read(output/'scenario/scenario.json')
    manifest['source_provenance'] = read(output/'source.json')
    manifest.pop('definition_sha256', None)
    manifest['definition_sha256'] = digest(encoded(manifest))
    write_json(output/'scenario/scenario.json', manifest)
    write_json(output/'bindings.json', {
        task['id']: {'scenario': str(output/'scenario'), 'reference': str(output/'reference')}})


if __name__ == '__main__':
    main()
