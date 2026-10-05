"""Report all decision-task reference trials without treating selected wins as reliability."""
import argparse
import html
import json
from pathlib import Path

from pokeagent_bench.core import write_json
from pokeagent_bench.decision_tasks import TASKS


def build(root, output):
    trials=json.loads((root/'decision-v1-validation-01/results.json').read_text())
    for variant in range(1,6):
        reference=root/f'decision-route-reference-{variant:02d}'
        result=json.loads((reference/'result.json').read_text())
        trials.append({'task':'recovery-detour','variant':f'variant-{variant:02d}',
                       'mode':'simulation-reference','completed':result['completed'],
                       'reason':result['stop_reason'],
                       'replay':json.loads((reference/'verification.json').read_text())})
        trials.append(json.loads((root/f'decision-route-direct-{variant:02d}/calibration.json').read_text()))
    rows=[]
    for task in TASKS:
        selected=[t for t in trials if t['task']==task['id']]
        reference=[t for t in selected if t['mode'] in ('tactical','simulation-reference')]
        baseline=[t for t in selected if t['mode'] in ('attack-first','skip-recovery-path')]
        rows.append({'id':task['id'],'name':task['name'],'reference_wins':sum(t['completed'] for t in reference),
                     'reference_trials':len(reference),'baseline_wins':sum(t['completed'] for t in baseline),
                     'baseline_trials':len(baseline),'replays_verified':all(t['replay']['verified'] for t in selected)})
    data={'status':'experimental','tasks':rows,'trials':trials,
          'method':'First fixed-policy sweep on five registered starts. Development data, not a held-out reliability estimate.',
          'caveats':['The route reference is the simulation policy with privileged access. It is not a model result.',
                     'Capture baseline throws balls immediately. Other battle baselines use direct damaging moves.',
                     'Route baseline replays the successful travel suffix from the same position but skips recovery.',
                     'Post-hoc winning-path searches prove feasibility only and are excluded from these win rates.',
                     'Five timing variants are paired starting conditions, not five guarantees of success or independent RNG streams.']}
    write_json(output.with_suffix('.json'),data)
    escape=lambda v:html.escape(str(v))
    table=''.join(f'<tr><td>{escape(t["name"])}</td><td>{t["reference_wins"]}/{t["reference_trials"]}</td><td>{t["baseline_wins"]}/{t["baseline_trials"]}</td><td>{escape(t["replays_verified"])}</td></tr>' for t in rows)
    notes=''.join(f'<li>{escape(c)}</li>' for c in data['caveats'])
    output.write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Decision suite calibration</title>'
                      '<body><main><h1>Six experimental decision benchmarks</h1><p><a href="pokemon-benchmarks.html">Benchmark portal</a></p>'
                      '<p>These tasks are excluded from the main ranking while calibration and model pilots are incomplete.</p>'
                      '<p>'+escape(data['method'])+'</p><table border="1" cellpadding="12"><thead><tr><th>Task</th><th>Reference wins</th><th>Simple baseline wins</th><th>Replays verified</th></tr></thead><tbody>'+table+'</tbody></table>'
                      '<h2>Interpretation</h2><ul>'+notes+'</ul><p><a href="'+output.with_suffix('.json').name+'">Download every sweep outcome</a></p></main></body></html>')
    return data


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    build(args.data,args.output)
