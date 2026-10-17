"""Copy checked starts for a catalog revision without changing old fixtures or results."""
import argparse
import json
from pathlib import Path
import shutil

from pokeagent_bench.core import digest, encoded, write_json
from pokeagent_bench.evaluation_catalog import load_catalog


def rebind(source, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    if output == source or source in output.parents:
        raise ValueError('Use a separate fixture root')
    shutil.copytree(source, output)
    definitions = {task['id']: task for group in load_catalog(include_retired=True) for task in group['evals']}
    changes = []
    for path in output.glob('**/scenario.json'):
        scenario = json.loads(path.read_text())
        task = definitions.get(scenario.get('task_id'))
        if task is None:
            continue
        old_hash = scenario.get('catalog_sha256')
        new_hash = digest(encoded(task))
        if old_hash == new_hash:
            continue
        state = path.parent / 'initial.state'
        if digest(state.read_bytes()) != scenario['state_sha256']:
            raise ValueError(f'Starting state changed: {path.parent.name}')
        scenario.update(catalog_sha256=new_hash, action_policy=task['action_policy'],
                        tested_skill=task['tested_skill'])
        if scenario.get('objective') and scenario['objective'].get('kind') == 'catalog-task':
            scenario['objective']['description'] = task['agent_goal']
        scenario['catalog_rebind'] = {'source': str(source / path.relative_to(output)),
                                     'previous_catalog_sha256': old_hash,
                                     'state_unchanged': True}
        write_json(path, scenario)
        changes.append(str(path.relative_to(output)))
    record = {'source': str(source), 'rebound': changes,
              'note': 'Native states unchanged. Prior proofs retain their original specification hashes and are not promoted to changed tasks.'}
    write_json(output / 'catalog-rebind.json', record)
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = rebind(args.source, args.output)
    print(f'Rebound {len(result["rebound"])} scenario definitions without changing saves')
