"""Export a sanitized static PokeBench snapshot into a new directory."""
import argparse
import json
from pathlib import Path

from pokeagent_bench.public_site import export_public


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--feed', type=Path, default=Path('data/reviews/pokemon-benchmarks.json'))
    parser.add_argument('--config', type=Path, default=Path('data/portal-config.json'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--report', type=Path, help='Reviewed public report PDF to include')
    parser.add_argument('--release-root', type=Path, help='Frozen protocol and release-summary.json directory')
    args = parser.parse_args()
    result = export_public(args.feed, args.config, args.output, args.report, args.release_root)
    print(json.dumps({key: result[key] for key in ('status', 'tasks', 'attempts', 'replays')}, indent=2))


if __name__ == '__main__':
    main()
