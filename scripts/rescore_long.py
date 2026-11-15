"""Score stored Long runs under the current campaign protocol by exact replay. Calls no model.

Each run still verifies under the protocol it was recorded with. The second score comes from the
same replayed frames and is written beside the run folder, never into the verified run files.
Usage: rescore_long.py --rom ROM DATA/long-run [DATA/long-run ...]
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
import re

from pokeagent_bench.campaign_runtime import VERSION
from pokeagent_bench.core import write_json
from pokeagent_bench.session import replay


def decision_stamps(run):
    """The decision and cumulative tokens for each action, as the live run stamped its awards."""
    tokens, total = {}, 0
    for line in (run / 'decisions.jsonl').read_text().splitlines():
        row = json.loads(line)
        usage = row.get('usage') or {}
        total += (usage.get('input_tokens') or 0) + (usage.get('output_tokens') or 0)
        tokens[row['index']] = total
    decisions = []
    for line in (run / 'actions.jsonl').read_text().splitlines():
        match = re.fullmatch(r'decision-(\d+)-.+', json.loads(line)['operation_id'])
        if not match:
            raise ValueError(f'{run}: an action has no decision index')
        decisions.append(int(match[1]))
    return decisions, tokens


def rescore(rom, root, version=VERSION):
    root = Path(root)
    run = root / 'run'
    verified = replay(Path(rom), run, rescore=version)
    report = verified.pop('rescore')
    decisions, tokens = decision_stamps(run)

    def stamp(row):
        decision = decisions[row['actions'] - 1]
        row.update(decision=decision, tokens=tokens[decision])

    for row in report['events'] + report['profiles'][1:]:
        stamp(row)
    for row in report['milestones']:
        if row['achievement']:
            stamp(row['achievement'])
    # Shared milestones use the same checks, so they must land on the recorded frames and stamps.
    recorded = json.loads((run / 'result.json').read_text())['campaign']
    old = {row['id']: row for row in recorded['events'] if row['kind'] == 'milestone'}
    new = {row['id']: row for row in report['events'] if row['kind'] == 'milestone'}
    for key, row in old.items():
        fields = ('frame', 'decision', 'tokens', 'actions')
        if key not in new or any(new[key][field] != row[field] for field in fields):
            raise ValueError(f'{root.name}: {key} differs from the recorded award')
    manifest = json.loads((run / 'manifest.json').read_text())
    output = {'format': 1, 'run': root.name, 'scoring_protocol': version,
              'recorded_protocol': manifest['scoring_protocol'], 'recorded_score': verified['score'],
              'score': report['score'], 'replay': verified,
              'note': 'Exact replay of the recorded inputs, scored under this protocol. The run itself '
                      'verifies under its recorded protocol. This file is not part of the verified run.',
              'campaign': report}
    path = root / f'{version}.json'
    write_json(path, output)
    added = sorted(set(new) - set(old))
    return {'run': root.name, 'recorded': verified['score'], 'score': report['score'],
            'milestones': len(new), 'added': added, 'path': str(path)}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--rom', required=True)
    parser.add_argument('--jobs', type=int, default=4)
    parser.add_argument('runs', nargs='+')
    args = parser.parse_args()
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        futures = [pool.submit(rescore, args.rom, root) for root in args.runs]
        for future in futures:
            row = future.result()
            print(f"{row['run']}: recorded {row['recorded']}, {VERSION} {row['score']}, "
                  f"{row['milestones']} milestones, {len(row['added'])} new", flush=True)


if __name__ == '__main__':
    main()
