"""Refresh the local focused leaderboard and optional paper input."""
import argparse
import time
from pokeagent_bench.focused_analysis import export

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--run', required=True)
parser.add_argument('--web', required=True)
parser.add_argument('--repeats')
parser.add_argument('--paper-input')
parser.add_argument('--watch', action='store_true', help='Refresh local results until the repeat phase stops')
args = parser.parse_args()
if args.watch and not args.repeats:
    parser.error('--watch requires --repeats')
while True:
    result = export(args.run, args.web, args.repeats, args.paper_input if not args.watch else None)
    print('Repeats:', result['repeats']['finished'], '/', result['repeats']['planned'], flush=True)
    if not args.watch or result['repeats']['status'] != 'running':
        if args.watch and args.paper_input:
            export(args.run, args.web, args.repeats, args.paper_input)
        break
    time.sleep(30)
