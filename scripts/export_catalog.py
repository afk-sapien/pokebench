"""Refresh the task catalog in an existing local results export."""
import argparse
import hashlib
import json
from pathlib import Path

from pokeagent_bench.catalog_portal import export_catalog


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--fixtures', type=Path, help='Show actual runtime and fixture readiness')
    args = parser.parse_args()
    output = args.output
    index = output / 'index.html'
    if not index.is_file():
        parser.error('Use an existing results export containing index.html')
    count = export_catalog(output, args.fixtures)
    page = index.read_text()
    page = page.replace('<a href="catalog.html">Task catalog</a>', '<a href="catalog.html">PokeBench tasks</a>')
    if 'href="pokebench-long.html"' not in page:
        page = page.replace('<nav>', '<nav><a href="pokebench-long.html">PokeBench Long</a>', 1)
    if 'href="catalog.html"' not in page:
        if '<nav>' not in page:
            raise ValueError('Results navigation was not found')
        page = page.replace('<nav>', '<nav><a href="catalog.html">PokeBench tasks</a>', 1)
    index.write_text(page)
    manifest_path = output / 'manifest.json'
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text())
        changed = ('index.html', 'catalog.html', 'catalog.json', 'pokebench-long.html', 'pokebench-long.json')
        rows = [row for row in manifest['files'] if row['path'] not in changed]
        for name in changed:
            raw = (output / name).read_bytes()
            rows.append({'path': name, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
        manifest['files'] = sorted(rows, key=lambda row: row['path'])
        manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'Exported {count} task specifications to {output / "catalog.html"}')


if __name__ == '__main__':
    main()
