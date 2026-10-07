"""Display available evidence without requiring complete cross-model coverage."""
from fractions import Fraction
import html


def available_snapshot(protocol, release, development, pilots=()):
    """Prefer verified release outcomes per model and task, otherwise curated history."""
    models = {m['model']: dict(m) for m in protocol['models']}
    for model in development['models']:
        models.setdefault(model['model'], {'model': model['model'], 'provider': 'unrecorded'})
    tasks = {t['id']: dict(t) for t in protocol['tasks']}
    for task in development['tasks']:
        tasks.setdefault(task['id'], {**task, 'score_eligible': task.get('included_in_score', False)})
    history = list(development['attempts'])
    for pilot in pilots:
        present = {(a['model'], a['task']) for a in history}
        history.extend(a for a in pilot['attempts'] if (a['model'], a['task']) not in present)
    cells = []
    for task in tasks.values():
        for model in models.values():
            current = [a for a in release['attempts'] if a['task'] == task['id'] and a['model'] == model['model']]
            recent = [a for a in current if a['status'] == 'finished' and a.get('replay_verified') is True
                      and a.get('accounting_complete') is True and type(a.get('completed')) is bool]
            old = [a for a in history if a['task'] == task['id'] and a['model'] == model['model']
                   and a['status'] == 'finished' and a.get('replay_verified') is True and type(a.get('completed')) is bool]
            selected = recent or old
            source = 'release' if recent else 'development' if old else None
            wins = sum(a['completed'] for a in selected)
            cells.append({'task': task['id'], 'model': model['model'], 'source': source,
                          'wins': wins, 'finished': len(selected),
                          'score': 100 * wins / len(selected) if selected else None,
                          'tokens': sum(a.get('tokens') or 0 for a in selected),
                          'release_finished': len(recent), 'release_planned': len(current),
                          'release_running': sum(a['status'] == 'running' for a in current),
                          'release_pending': sum(a['status'] in ('pending', 'paused') for a in current),
                          'release_errors': sum(a['status'] == 'error' for a in current),
                          'attempts': [{key: a[key] for key in ('id', 'completed', 'tokens', 'variant', 'repeat', 'benchmark', 'replay', 'source_cohort', 'recovery_of', 'recovery_adapter') if key in a}
                                       for a in selected]})
    eligible = {t['id'] for t in tasks.values() if t['score_eligible']}
    rows = []
    for model in models.values():
        observed = [c for c in cells if c['model'] == model['model'] and c['finished'] and c['task'] in eligible]
        rate = sum((Fraction(c['wins'], c['finished']) for c in observed), Fraction()) / len(observed) if observed else None
        rows.append({**model, 'score': float(100 * rate) if rate is not None else None,
                     'tested': len(observed), 'eligible': len(eligible),
                     'wins': sum(c['wins'] for c in observed), 'finished': sum(c['finished'] for c in observed),
                     'release_tasks': sum(c['source'] == 'release' for c in observed),
                     'development_tasks': sum(c['source'] == 'development' for c in observed)})
    rows.sort(key=lambda row: (row['score'] is None, -(row['score'] or 0), -row['tested'], row['model']))
    return {'policy': 'available-results-equal-task-weight-v1', 'models': rows,
            'tasks': [{'id': t['id'], 'name': t['name'], 'difficulty': t['difficulty'], 'score_eligible': t['score_eligible']} for t in tasks.values()],
            'cells': cells, 'eligible': len(eligible)}


def available_section(data, release):
    e = html.escape
    text = '<section id="controlled-evaluation"><h2>Overall leaderboard <span class="small muted">All available results</span></h2>'
    text += '<p>'+str(len(data['tasks']))+' benchmarks · '+str(len(data['models']))+' models · '+str(data['eligible'])+' scored benchmarks</p>'
    text += '<p class="small muted">Observed scores use each model’s tested benchmarks, with equal weight per benchmark. Coverage differs, so this ordering is descriptive, not a fair head-to-head rank. Missing tests are not losses. Current release results replace older results for each model and benchmark as they arrive. Older results use different framework versions.</p>'
    text += '<div class="cost-scroll"><table class="cost-table available-board"><thead><tr><th>Model</th><th>Provider</th><th>Observed score</th><th>Benchmarks tested</th><th>Passes / trials</th><th>Evidence</th></tr></thead><tbody>'
    for row in data['models']:
        score = f"{row['score']:.1f}%" if row['score'] is not None else 'Not tested'
        provider = {'codex': 'OpenAI', 'claude': 'Anthropic'}.get(row['provider'], row['provider'])
        evidence = str(row['release_tasks'])+' current / '+str(row['development_tasks'])+' earlier'
        text += '<tr><th scope="row">'+e(row['model'])+'</th><td>'+e(provider)+'</td><td><strong>'+score+'</strong></td><td>'+str(row['tested'])+' / '+str(row['eligible'])+'</td><td>'+str(row['wins'])+' / '+str(row['finished'])+'</td><td class="small">'+e(evidence)+'</td></tr>'
    text += '</tbody></table></div><p class="small">Current evaluation: '+e(release['status'])+' · '+str(release['finished'])+' finished trials · '+str(release['running'])+' running. <a href="available-results.json">All-results JSON</a> · <a href="available-leaderboard.csv" download>Leaderboard CSV</a> · <a href="#matched-comparison">Compare identical starts</a></p></section>'
    return text



def evaluation_status(cell):
    """Describe observed evidence, never treat unused repeat slots as required work."""
    if cell['finished']:
        n = cell['finished']
        status = f"Evaluated · {n} completed trial" + ('s' if n != 1 else '')
        if cell['release_running']:
            status += ' · additional trial running'
    elif cell['release_running']:
        status = 'Running'
    elif cell['release_errors']:
        status = 'Evaluation error · no valid result'
    else:
        status = 'Not evaluated'
    if cell['release_errors']:
        n = cell['release_errors']
        status += f" · {n} recorded error" + ('s' if n != 1 else '')
    return status


def benchmark_section(data):
    e = html.escape
    text = '<section id="benchmarks"><h2>All benchmarks</h2><p class="small muted">Every benchmark stays visible. Open one to see every model, including models not yet evaluated. Experimental tasks are shown but excluded from the leaderboard score.</p>'
    text += '<input id="suite-search" type="search" aria-label="Search all benchmarks" placeholder="Search benchmarks"><p id="suite-count" class="small">'+str(len(data['tasks']))+' benchmarks</p>'
    for task in data['tasks']:
        cells = [c for c in data['cells'] if c['task'] == task['id']]
        tested = sum(bool(c['finished']) for c in cells)
        label = 'Scored' if task['score_eligible'] else 'Experimental'
        text += '<details class="suite-task" data-name="'+e(task['name'].lower(), quote=True)+'"><summary><strong>'+e(task['name'])+'</strong><span class="small muted"> '+e(task['difficulty'])+' · '+str(tested)+' / '+str(len(cells))+' models tested · '+label+'</span></summary><div class="cost-scroll"><table class="cost-table available-board"><thead><tr><th>Model</th><th>Result</th><th>Passes / trials</th><th>Evidence</th><th>Status</th></tr></thead><tbody>'
        for cell in cells:
            result = f"{cell['score']:.1f}%" if cell['score'] is not None else 'Not tested'
            source = {'release': 'Current release', 'development': 'Earlier development', None: 'No result'}[cell['source']]
            progress = evaluation_status(cell)
            text += '<tr><th scope="row">'+e(cell['model'])+'</th><td>'+result+'</td><td>'+str(cell['wins'])+' / '+str(cell['finished'])+'</td><td>'+source+'</td><td class="small">'+progress+'</td></tr>'
        text += '</tbody></table></div><p class="small"><a href="benchmarks/'+e(task['id'])+'.html">Attempt details and archived replays</a></p></details>'
    text += '</section><script>document.getElementById("suite-search").addEventListener("input", event => {\nconst query = event.target.value.toLowerCase().trim()\nlet visible = 0\nfor (const row of document.querySelectorAll(".suite-task")) {\nrow.hidden = !row.dataset.name.includes(query)\nif (!row.hidden) visible += 1\n}\ndocument.getElementById("suite-count").textContent = visible + " benchmarks"\n})</script>'
    return text
