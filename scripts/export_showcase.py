"""Build or refresh the local PokeBench showcase without changing any runs."""
import argparse
import time
from pokeagent_bench.showcase import export, root_map

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--data', required=True)
parser.add_argument('--web', required=True)
parser.add_argument('--watch', action='store_true')
parser.add_argument('--sources', help='Rerun source map to use instead of the checked-in showcase_sources/rerun-sources.json')
parser.add_argument('--root', action='append', default=[], metavar='NAME=FOLDER',
                    help='The folder of a root that maintainer rows name. Repeat it for each root. '
                         'A row whose root is not given is left off the site.')
args = parser.parse_args()
try:
    roots = root_map(args.root)
except ValueError as error:
    parser.error(f'--root {error}')
first = True
while True:
    result = export(args.data, args.web, install=first, sources=args.sources, roots=roots)
    first = False
    print(result['updated_at'], result['short']['finished'], '/', result['short']['planned'], flush=True)
    if not args.watch or (result['short']['finished'] == result['short']['planned']
                          and all(r['state'] == 'finished' and all(e['state'] == 'finished' for e in r.get('extensions', []))
                                  for r in result['long'])):
        break
    time.sleep(60)
