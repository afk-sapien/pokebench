"""Sanitized versioned suite coverage reports and a local HTML results page."""
import base64
import csv
import html
from pathlib import Path
import statistics

from .core import write_json, digest
from .suite import DEFINITION, read, validate, accounted


def summarize(batch, definition=None):
    definition = definition or DEFINITION
    tasks = definition['tasks']
    result = {"suite": definition['id'], "development": True, "phase": batch['phase'],
              "budget": batch['budget'], "tokens": accounted(batch['cells']), "models": [], "tasks": tasks,
              "configuration": batch['configuration'], "attempts": []}
    for cell in batch['cells']:
        result['attempts'].append({key:cell[key] for key in
            ('id','model','task','repeat','variant','status','tokens','error','retained_from') if key in cell} | {
                'completed':cell.get('result', {}).get('completed') if cell['status']=='finished' else None,
                'stop_reason':cell.get('result', {}).get('stop_reason'),
                'wall_seconds':cell.get('result', {}).get('wall_seconds'),
                'replay_verified':cell.get('replay', {}).get('verified', False),
                'decisions':cell.get('result', {}).get('usage', {}).get('calls')})
    for model in batch['models']:
        cells = [c for c in batch['cells'] if c['model']==model]
        finished = [c for c in cells if c['status']=='finished' and c.get('replay',{}).get('verified')]
        by_task = {}
        for task in tasks:
            attempts = [c for c in finished if c['task']==task['id']]
            successes = [c for c in attempts if c['result']['completed']]
            by_task[task['id']] = {'successes':len(successes), 'finished':len(attempts),
                                  'planned':sum(c['task']==task['id'] for c in cells),
                                  'tokens':sum(c.get('tokens',0) for c in cells if c['task']==task['id']),
                                  'median_success_tokens':statistics.median([c['tokens'] for c in successes]) if successes else None}
        complete = bool(cells) and len(finished)==len(cells) and all(t['finished'] for t in by_task.values())
        score = (100*statistics.mean(t['successes']/t['finished'] for t in by_task.values())) if complete else None
        result['models'].append({'model':model, 'score':score, 'complete':complete, 'tasks':by_task,
                                 'finished':len(finished), 'planned':len(cells),
                                 'tokens':sum(c.get('tokens',0) for c in cells),
                                 'errors':sum(c['status']=='error' for c in cells)})
    ready = bool(result['models']) and all(model['complete'] for model in result['models'])
    result['ranking_ready'] = ready
    result['models'].sort(key=lambda model: (model['score'] is None, -(model['score'] or 0), model['model']))
    for model in result['models']:
        model['rank'] = (1 + sum(other['score'] > model['score'] for other in result['models'])) if ready else None
    return result


def export_report(suite_root, batch_root, output, historical_runs=()):
    suite = validate(suite_root, require_runtime=False)
    batch = read(Path(batch_root)/'batch.json') if batch_root else {
        'models':[], 'cells':[], 'phase':'Fixtures verified. No suite model trials yet.', 'budget':0,
        'configuration':{'suite_definition':suite['definition_sha256'],
                         'suite_sha256':digest((Path(suite_root)/'suite.json').read_bytes()),
                         'core':suite['core'], 'rom_sha256':suite['rom_sha256']}}
    if batch_root and batch['configuration']['suite_sha256'] != digest((Path(suite_root)/'suite.json').read_bytes()):
        raise ValueError('Report suite does not match batch')
    if batch_root:
        for cell in batch['cells']:
            path = Path(batch_root)/cell['id']/'result.json'
            if cell['status'] in ('running', 'paused') and path.exists():
                cell['result'] = read(path)
                usage = cell['result']['usage']
                cell['tokens'] = usage['input_tokens'] + usage['output_tokens']
    definition = suite['definition']
    tasks = definition['tasks']
    report = summarize(batch, definition)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    report['historical_pilots'] = []
    for source in historical_runs:
        source = Path(source)
        manifest, result = read(source/'manifest.json'), read(source/'result.json')
        if result['state'] != 'finished':
            continue
        report['historical_pilots'].append({'run':source.name, 'model':manifest['agent']['model'],
            'completed':result['completed'], 'tokens':result['usage']['input_tokens']+result['usage']['output_tokens'],
            'calls':result['usage']['calls'], 'benchmark':manifest['benchmark'],
            'source_sha256':manifest['source_sha256'], 'stop_reason':result['stop_reason']})
    write_json(output.with_suffix('.json'), report)
    with output.with_suffix('.csv').open('w', newline='') as stream:
        fields=['id','model','task','repeat','variant','status','completed','tokens','wall_seconds','stop_reason','replay_verified','decisions']
        writer=csv.DictWriter(stream, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(report['attempts'])
    e=lambda value:html.escape(str(value), quote=True)
    styles={
        'body':{'margin':'0','background':'#0b1120','color':'#e8edf5','font-family':'system-ui, sans-serif'},
        'main':{'max-width':'1200px','margin':'auto','padding':'40px 24px 80px'},
        'h1':{'font-size':'38px','letter-spacing':'-1px','margin-bottom':'8px'},
        'h2':{'margin-top':'36px','font-size':'23px'},
        'p':{'line-height':'1.6'},
        'a':{'color':'#78d8ce'},
        '.muted':{'color':'#a4b1c6'},
        '.badge':{'display':'inline-block','padding':'6px 11px','border':'1px solid #345168','border-radius':'20px','color':'#78d8ce'},
        '.cards':{'display':'grid','grid-template-columns':'repeat(auto-fit, minmax(180px, 1fr))','gap':'14px','margin':'28px 0'},
        '.card, details':{'padding':'20px','background':'#121e30','border':'1px solid #263449','border-radius':'12px'},
        '.number':{'font-size':'30px','font-weight':'700'},
        '.table-wrap':{'overflow-x':'auto','background':'#121e30','border':'1px solid #263449','border-radius':'12px'},
        'table':{'width':'100%','border-collapse':'collapse','text-align':'left'},
        'th, td':{'padding':'15px 18px','border-bottom':'1px solid #263449','vertical-align':'top'},
        'th':{'color':'#a4b1c6','font-size':'13px'},
        '.pass':{'color':'#78d8ce'},
        '.fail':{'color':'#ffb1a3'},
        'details':{'margin-top':'12px'},
        'summary':{'cursor':'pointer','font-weight':'600'},
        'nav':{'display':'flex','gap':'20px','flex-wrap':'wrap','margin-top':'24px'},
        'thead th':{'position':'sticky','top':'0','background':'#121e30'},
        'tbody td:first-child':{'position':'sticky','left':'0','background':'#121e30','min-width':'140px'},
    }
    css='\n'.join(f'{selector} {{{key}:{value}}}' for selector,props in styles.items() for key,value in props.items())
    parts=[f'<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>PokeAgent Bench | Model rankings</title><style>{css}</style><main>',
           f'<span class="badge">DEVELOPMENT SUITE · {e(definition["id"].upper())}</span><h1>Pokemon model rankings</h1>',
           f'<p class="muted">{len(tasks)} fixed checkpoints. Verified game outcomes. Every model gets the same task settings.</p>',
           '<nav><a href="#results">Results</a><a href="#tasks">Tasks and fixtures</a><a href="#attempts">Attempts</a>',
           f'<a href="{e(output.with_suffix(".json").name)}" download>Download JSON</a><a href="{e(output.with_suffix(".csv").name)}" download>Download CSV</a></nav>',
           f'<div class="cards"><div class="card"><div class="number">{len(tasks)} / {len(tasks)}</div>Verified fixtures</div>',
           f'<div class="card"><div class="number">{sum(m["finished"] for m in report["models"])} / {len(report["attempts"])}</div>Finished suite attempts</div>',
           f'<div class="card"><div class="number">{report["tokens"]:,}</div>Reported tokens consumed</div></div>',
           f'<p class="muted">{e(report["phase"])}. Subscription dollar cost is unavailable.</p>',
           '<h2 id="results">Model results</h2><p>Rankings appear after every model finishes the same registered tasks and repeats. Equal completion scores share a rank. Token usage is shown separately. One attempt per task is a preliminary comparison, not a reliability estimate.</p>',
           '<div class="table-wrap"><table><thead><tr><th>Model / rank</th><th>Overall</th>']
    parts.extend(f'<th>{e(t["name"])}</th>' for t in tasks)
    parts.append('<th>Tokens</th></tr></thead><tbody>')
    for model in report['models']:
        score=f'{model["score"]:.1f}%' if model['score'] is not None else 'Incomplete'
        rank = f'#{model["rank"]}' if model['rank'] is not None else 'Awaiting full coverage'
        parts.append(f'<tr><td><strong>{e(model["model"])}</strong><br><small class="muted">{rank}</small></td><td>{score}</td>')
        for task in tasks:
            cell=model['tasks'][task['id']]
            text=f'{cell["successes"]}/{cell["finished"]} passed' if cell['finished'] else 'Pending'
            parts.append(f'<td>{text}<br><small class="muted">{cell["finished"]}/{cell["planned"]} finished</small></td>')
        parts.append(f'<td>{model["tokens"]:,}</td></tr>')
    if not report['models']:
        parts.append(f'<tr><td colspan="{len(tasks)+3}">No scored suite batch yet. Fixture reference checks do not count as model performance.</td></tr>')
    parts.append('</tbody></table></div>')
    provenance = report['configuration']
    core = provenance.get('core', {})
    parts.append(f'<details><summary>Comparison protocol and provenance</summary><p>Equal task weights. All registered attempts count. Infrastructure errors prevent ranking and are not treated as gameplay failures.</p><p>Core {e(core.get("version", "unavailable"))}. Source {e(provenance.get("source_sha256", "unavailable"))}. Medium reasoning effort, bounded eight-turn context, no paid summaries.</p></details>')
    parts.append('<h2 id="tasks">Tasks and fixtures</h2>')
    for task in tasks:
        fixture=suite['fixtures'][task['id']]
        manifest=read(Path(suite_root)/fixture['scenario']/'scenario.json')
        preview_path = Path(suite_root)/fixture['scenario']/'preview.png'
        preview = ''
        if preview_path.exists():
            data = base64.b64encode(preview_path.read_bytes()).decode('ascii')
            preview = f'<img src="data:image/png;base64,{data}" width="240" height="216" alt="{e(task["name"])} starting screen">'
        parts.append(f'<details><summary>{e(task["name"])} · {task["difficulty"].title()} · {task["tokens"]:,} token ceiling</summary><p>{e(manifest["objective"]["description"])}</p>{preview}<p class="muted">Successful controller reference and no-input negative replay verified. Starting save: {e(fixture["state_sha256"][:16])}. Reference controllers are offline fixture checks, not model results.</p></details>')
    parts.append('<h2 id="attempts">Suite attempts</h2><div class="table-wrap"><table><thead><tr><th>Model / task</th><th>Attempt</th><th>Outcome</th><th>Tokens / decisions</th><th>Review</th></tr></thead><tbody>')
    for attempt in report['attempts']:
        review='Not available'
        run=Path(batch_root)/attempt['id']
        if attempt['status']=='finished' and (run/'decisions.jsonl').exists():
            from .review import export_review
            revision=digest((run/'manifest.json').read_bytes()+(run/'result.json').read_bytes())[:16]
            target=output.parent/(output.stem+'-'+attempt['id']+'-'+revision+'.html')
            if not target.exists():
                export_review([run], target)
            review=f'<a href="{e(target.name)}">Watch decisions</a>'
        outcome=('Passed' if attempt['completed'] else 'Failed') if attempt['completed'] is not None else attempt['status'].title()
        parts.append(f'<tr><td>{e(attempt["model"])}<br>{e(attempt["task"])}</td><td>{attempt["repeat"]}</td><td>{outcome}<br><small class="muted">{e(attempt["stop_reason"] or "")}</small></td><td>{attempt.get("tokens",0):,}<br><small class="muted">{attempt.get("decisions") or 0} decisions</small></td><td>{review}</td></tr>')
    parts.append('</tbody></table></div>')
    if report['historical_pilots']:
        parts.append('<h2>Earlier starter pilots</h2><p class="muted">Historical context only. These runs are excluded from suite scores because they used earlier runtime configurations.</p><div class="table-wrap"><table><tr><th>Model</th><th>Outcome</th><th>Tokens</th><th>Decisions</th></tr>')
        for row in report['historical_pilots']:
            parts.append(f'<tr><td>{e(row["model"])}</td><td>{"Passed" if row["completed"] else "Failed"}</td><td>{row["tokens"]:,}</td><td>{row["calls"]}</td></tr>')
        parts.append('</table></div>')
    parts.append('<p class="muted">Score: mean of per-task completion rates, with equal task weight. No best-of-repeat selection. Missing tasks and infrastructure errors remain visible. Healing measures HP and status recovery, not PP restoration. This page is a decision-review index, not continuous video.</p></main></html>')
    if any(attempt['status'] in ('pending', 'running', 'paused') for attempt in report['attempts']) and report['phase'] not in ('stopped for error', 'stopped after in-flight budget overrun'):
        parts[0] = parts[0].replace('<meta charset="utf-8">', '<meta charset="utf-8"><meta http-equiv="refresh" content="30">')
    output.write_text('\n'.join(parts))
    return {'html':str(output.resolve()), 'json':str(output.with_suffix('.json').resolve()), 'models':report['models']}
