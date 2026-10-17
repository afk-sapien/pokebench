"""Build or refresh the local PokeBench showcase without changing any runs."""
import argparse
import time
from pokeagent_bench.showcase import export

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--data', required=True)
parser.add_argument('--web', required=True)
parser.add_argument('--watch', action='store_true')
args = parser.parse_args()
first = True
while True:
    result = export(args.data, args.web, install=first)
    first = False
    print(result['updated_at'], result['short']['finished'], '/', result['short']['planned'], flush=True)
    if not args.watch or (result['short']['finished'] == result['short']['planned']
                          and all(r['state'] == 'finished' and all(e['state'] == 'finished' for e in r.get('extensions', []))
                                  for r in result['long'])):
        break
    time.sleep(60)
