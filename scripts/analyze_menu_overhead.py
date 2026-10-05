"""Count recorded menu overhead without inferring strategy or counterfactual wins."""
import argparse
from collections import defaultdict
import json
from pathlib import Path

from pokeagent_bench.core import write_json


def analyze(run):
    rows = [json.loads(line) for line in (run/'decisions.jsonl').read_text().splitlines()]
    buckets = defaultdict(lambda: {'decisions':0, 'tokens':0})
    for row in rows:
        usage = row['usage']['input_tokens'] + row['usage']['output_tokens']
        actions = row['decision']['actions']
        if len(actions) != 1:
            continue
        action = actions[0]
        screen = row['provider']['context']['game']['screen']
        labels = []
        if action['command'] == 'press':
            labels.append('all_single_presses')
            if action['argument'] in ('up', 'down', 'left', 'right') and screen['kind'] in ('menu', 'move_menu', 'battle_menu'):
                labels.append('directional_menu_presses')
        if action['command'] == 'choose' and action['argument'] == 'FIGHT':
            labels.append('fight_openers')
        for label in labels:
            buckets[label]['decisions'] += 1
            buckets[label]['tokens'] += usage
    manifest = json.loads((run/'manifest.json').read_text())
    return {'run':str(run.resolve()), 'model':manifest['agent']['model'], 'decisions':len(rows),
            'tokens':sum(r['usage'][k] for r in rows for k in ('input_tokens','output_tokens')),
            'categories':dict(buckets)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, nargs='+', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = {'runs':[analyze(run) for run in args.run],
              'method':'Reported input including cached input plus output. Categories overlap. '
                       'Directional menu presses are a subset of single presses. These are observed '
                       'costs, not a prediction of tokens saved or model success.'}
    write_json(args.output, report)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
