"""One focused catalog pass with a small bounded pool of subscription workers."""
from collections import Counter
from html import escape
import json
import fcntl
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from .catalog_batch import accounting_complete, cell_result, plan, report, token_usage
from .core import digest, write_json

RESERVE = 64000


def choose_cell(cells, states, running, results, workers, provider_workers):
    """Check one model per start before expanding that start to the other models."""
    if len(running) >= workers:
        return None
    counts = Counter(cell['provider'] for cell in cells if cell['id'] in running)
    groups = {}
    for cell in cells:
        groups.setdefault((cell['task_id'], cell['variant']), []).append(cell)
    pilots = {group[0]['id'] for group in groups.values()}
    candidates = []
    for cell in cells:
        if states[cell['id']] != 'pending' or counts[cell['provider']] >= provider_workers:
            continue
        group = groups[(cell['task_id'], cell['variant'])]
        if any(states[c['id']] == 'evaluation_error' for c in group):
            continue
        pilot = group[0]
        if cell['id'] != pilot['id']:
            result = results.get(pilot['id'])
            if states[pilot['id']] != 'finished' or result is None or not accounting_complete(result):
                continue
        candidates.append(cell)
    return min(candidates, key=lambda c: (c.get('dispatch_priority', 0), not c.get('replacement_condition'), c['id'] not in pilots, c['decision_limit'], cells.index(c))) if candidates else None


def ledger(cells, states, running, results):
    spent = 0
    reserved = 0
    unknown = []
    for cell in cells:
        key = cell['id']
        raw = results.get(key)
        used = token_usage(raw) if raw else 0
        if key in running:
            reserved += max(cell['token_limit'] + RESERVE, used)
        elif states[key] != 'pending':
            spent += used
            if raw is None or not accounting_complete(raw):
                unknown.append(key)
    return spent, reserved, unknown



def budget_adjustments(root, cells, results, unknown):
    """Carry archived charges and explicitly reserved missing usage without inventing tokens."""
    source = Path(root) / 'budget-adjustments.json'
    if not source.exists():
        return 0, 0, unknown
    record = json.loads(source.read_text())
    carried = record.get('archived_reported_tokens', 0)
    if type(carried) is not int or carried < 0:
        raise ValueError('Invalid archived token debit')
    reserves = record.get('unreported_usage_reserves', {})
    by_id = {cell['id']: cell for cell in cells}
    extra = record.get('archived_unreported_usage_reserve', 0)
    if type(extra) is not int or extra < 0:
        raise ValueError('Invalid archived missing usage reserve')
    unresolved = []
    for key in unknown:
        reserve = reserves.get(key)
        raw = results.get(key)
        if reserve is None or raw is None:
            unresolved.append(key)
            continue
        # This is a conservative spending reserve, never measured model usage.
        required = by_id[key]['token_limit'] + RESERVE
        if (type(reserve.get('total_upper_bound')) is not int
                or reserve['total_upper_bound'] < required
                or reserve.get('reported_tokens') != token_usage(raw)
                or not reserve.get('evidence')):
            raise ValueError('Missing usage reserve does not cover the full attempt allowance')
        extra += max(0, reserve['total_upper_bound'] - token_usage(raw))
    return carried, extra, unresolved


def export_progress(root, web, progress):
    web.mkdir(parents=True, exist_ok=True)
    write_json(web / 'focused-pass-v056.json', progress)
    models = []
    for model in progress['models']:
        score = model['available_category_average']
        models.append('<tr><th>' + escape(model['model']) + '</th><td>' +
            (f'{score:.1%}' if score is not None else 'Pending') + '</td><td>' +
            f"{model['completed']} / {model['planned']}</td><td>{model['evaluation_errors']}</td><td>{model['tokens']:,}</td></tr>")
    tasks = {}
    for cell in progress['cells']:
        tasks.setdefault((cell['category'], cell['task_id']), []).append(cell)
    sections = []
    for (category, task), cells in tasks.items():
        lines = []
        for cell in cells:
            decisions = cell.get('decisions')
            value = cell['value']
            outcome = f'{value:.0%}' if value is not None else cell['state'].replace('_', ' ')
            revision = cell.get("attempt_revision") or ("v057" if cell.get("replacement_condition") else "v056")
            replay = web / 'replays' / f"focused-{revision}-{cell['id']}.html"
            source = root / cell['id']
            if cell['state'] in ('finished', 'evaluation_error') and (source / 'manifest.json').exists() and not replay.exists():
                from .review import review_html
                try:
                    replay.parent.mkdir(exist_ok=True)
                    replay.write_text(review_html([source], seconds=30))
                except (ValueError, KeyError, OSError):
                    pass
            link = f'<a href="replays/{replay.name}">Replay</a>' if replay.exists() else ''
            if cell.get('previous_replay'):
                old_replay = web / 'replays' / Path(cell['previous_replay']).name
                if old_replay.exists():
                    link += f' <a href="replays/{old_replay.name}">Previous error</a>'
            if cell.get('replacement_condition'):
                old_replay = web / 'replays' / f"focused-v056-{cell['id']}.html"
                if old_replay.exists():
                    link += f' <a href="replays/{old_replay.name}">Original with battles</a>'
            lines.append(f"<tr><th>{escape(cell['model'])}</th><td>{escape(cell['variant'])}</td><td>{escape(outcome)}</td><td>{decisions if decisions is not None else '?'} / {cell['decision_limit']}</td><td>{cell['tokens']:,} / {cell['token_limit']:,}</td><td>{link}</td></tr>")
        sections.append(f'<details><summary>{escape(category)}: {escape(task)}</summary><table><thead><tr><th>Model</th><th>Start</th><th>Result</th><th>Decisions</th><th>Tokens</th><th>Evidence</th></tr></thead><tbody>{"".join(lines)}</tbody></table></details>')
    finished = sum(c['state'] == 'finished' for c in progress['cells'])
    active = sum(c['state'] == 'running' for c in progress['cells'])
    page = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta http-equiv="refresh" content="30"><title>PokeBench initial focused pass</title><style>
body {font-family:system-ui,sans-serif} body {background:#101923} body {color:#eaf0f5} body {max-width:1200px} body {margin:32px auto} body {padding:0 24px}
a {color:#a6e8ba} p {line-height:1.6} table {width:100%} table {border-collapse:collapse} th {text-align:left} td,th {padding:12px} tr {border-bottom:1px solid #304353} details {margin:18px 0} summary {cursor:pointer} nav {display:flex} nav {gap:24px}
</style><nav><a href="index.html">All results</a><a href="catalog.html">Tasks and budgets</a><a href="focused-pass-v056.json">Download results</a></nav><h1>PokeBench: initial focused pass</h1>'''
    page += f"<p><strong>{finished} / {len(progress['cells'])} attempts finished. {active} running.</strong> {progress['tokens_used']:,} reported tokens. Shared spending backstop: {progress['token_budget']:,}. Status: {escape(progress['status'])}.</p>"
    if progress.get('archived_reported_tokens') or progress.get('unreported_usage_reserve'):
        page += f"<p>Usage includes {progress.get('archived_reported_tokens', 0):,} tokens from archived original attempts. An additional {progress.get('unreported_usage_reserve', 0):,} tokens are reserved for interrupted calls with missing usage. This reserve is not measured usage. Four navigation tasks now exclude battles. Original attempts remain archived.</p>"
    page += '<p>One attempt per registered start, equal decision allowances across models, current-only screenshots. Preparation scores are fixed-controller win rates. Other task scores are completion rates. Available category averages exclude pending work and infrastructure errors. Compare coverage before ranking. PokeBench Long is not included.</p>'
    page += '<table><thead><tr><th>Model</th><th>Available score</th><th>Finished</th><th>Errors</th><th>Tokens</th></tr></thead><tbody>' + ''.join(models) + '</tbody></table><h2>Tasks</h2>' + ''.join(sections)
    page += '</html>'
    temporary = web / 'focused-pass-v056.html.tmp'
    temporary.write_text(page)
    temporary.replace(web / 'focused-pass-v056.html')


def effective_budget(root, manifest):
    original = manifest['token_budget']
    source = Path(root) / 'budget-ceiling.json'
    if not source.exists():
        return original
    limit = json.loads(source.read_text()).get('total_token_budget')
    if type(limit) is not int or not 0 < limit <= original:
        raise ValueError('A ceiling amendment can only reduce the recorded spending backstop')
    return limit


def _run_pass(fixtures, rom, game_data, output, web, models, *, budget, workers=4, provider_workers=2, resume=False):
    """Persist all work and never retry a charged or interrupted attempt implicitly."""
    if type(budget) is not int or budget <= 0 or workers < 1 or provider_workers < 1:
        raise ValueError('Positive budgets and worker counts are required')
    root = Path(output).resolve()
    if resume:
        manifest = json.loads((root / 'plan.json').read_text())
        if effective_budget(root, manifest) != budget:
            raise ValueError('Resume must retain the recorded shared token ceiling')
    else:
        source = Path(__file__).resolve().parents[1]
        shutil.copytree(source / 'pokeagent_bench', root / 'runtime' / 'pokeagent_bench',
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        manifest = plan(fixtures, models)
        # Alternate strong pilot providers across starts, preserving all registered cells.
        groups = {}
        for cell in manifest['cells']:
            groups.setdefault((cell['task_id'], cell['variant']), []).append(cell)
        ordered = []
        for index, group in enumerate(groups.values()):
            preferred = 'codex' if index % 2 == 0 else 'claude'
            ordered.extend(sorted(group, key=lambda c: c['provider'] != preferred))
        manifest['cells'] = ordered
        manifest.update(token_budget=budget, workers=workers, provider_workers=provider_workers,
            fixtures=str(Path(fixtures).resolve()), started_at=time.time(), repeats=1,
            runtime_files={str(p.relative_to(root / 'runtime')): digest(p.read_bytes())
                for p in (root / 'runtime').rglob('*') if p.is_file()},
            notes=['One pilot per native start before other models on that start',
                   'Model failures are results. Infrastructure errors hold that task for investigation',
                   'Unknown token charges halt new dispatch. No automatic paid retries',
                   'Equal task caps. Shared backstop may leave explicit pending cells',
                   'PokeBench Long excluded'])
        write_json(root / 'plan.json', manifest)
    cells = manifest['cells']
    current = report(root)
    states = {c['id']: c['state'] for c in current['cells']}
    if any(state not in ('pending', 'finished', 'evaluation_error') for state in states.values()):
        raise ValueError('Resume requires unfinished model workers to finish or be explicitly recovered first')
    running = {}
    results = {c['id']: raw for c in cells if (raw := cell_result(root / c['id'])) is not None}
    if any((root / c['id']).exists() and c['id'] not in results for c in cells):
        raise ValueError('An existing worker directory has no accounted result. Inspect before resuming')
    env = os.environ.copy()
    env['PYTHONPATH'] = str(root / 'runtime')
    status = 'running'
    last_export = 0
    while True:
        repaired = [key for key, state in states.items() if state == 'evaluation_error'
                    and (root / key / 'reassessment.json').exists()]
        if repaired:
            refreshed = {row['id']: row for row in report(root)['cells']}
            for key in repaired:
                states[key] = refreshed[key]['state']
                results[key] = cell_result(root / key)
        for key, (process, log) in list(running.items()):
            raw = cell_result(root / key)
            if raw is not None:
                results[key] = raw
            if process.poll() is None:
                continue
            log.close()
            del running[key]
            if process.returncode or raw is None or raw.get('state') in ('running', 'paused', 'interrupted'):
                destination = root / key
                destination.mkdir(exist_ok=True)
                prior_error = destination / 'error.json'
                if prior_error.exists():
                    shutil.copy2(prior_error, destination / 'worker-error.json')
                write_json(destination / 'error.json', {'evaluation_error': 'Worker stopped before a clean completion. Inspect worker log.',
                    'usage': raw.get('usage', {}) if raw else {'accounting_complete': False}})
                results[key] = cell_result(destination)
            result_row = next(row for row in report(root)['cells'] if row['id'] == key)
            states[key] = result_row['state']
        budget = min(budget, effective_budget(root, manifest))
        spent, reserved, unknown = ledger(cells, states, running, results)
        carried, missing_reserve, unknown = budget_adjustments(root, cells, results, unknown)
        spent += carried
        reserved += missing_reserve
        if (root / 'pause.dispatch').exists():
            status = 'dispatch paused'
        elif unknown:
            status = 'accounting needs inspection'
        else:
            while True:
                cell = choose_cell(cells, states, running, results, workers, provider_workers)
                if cell is None:
                    break
                if spent + reserved + cell['token_limit'] + RESERVE > budget:
                    status = 'shared token backstop reached'
                    break
                destination = root / cell['id']
                command = [sys.executable, '-m', 'pokeagent_bench', 'catalog-run',
                    '--fixtures', str(fixtures), '--rom', str(rom), '--game-data', str(game_data),
                    '--output', str(destination), '--task', cell['task_id'], '--variant', cell['variant'],
                    '--provider', cell['provider'], '--model', cell['model'],
                    '--decision-limit', str(cell['decision_limit']), '--token-limit', str(cell['token_limit']),
                    '--reasoning-effort', 'low', '--presentation', 'current']
                log = (root / (cell['id'] + '.log')).open('w')
                process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, env=env, cwd=root)
                running[cell['id']] = (process, log)
                states[cell['id']] = 'running'
                status = 'running'
                reserved += cell['token_limit'] + RESERVE
                print(json.dumps({'started': cell['id'], 'task': cell['task_id'], 'model': cell['model']}), flush=True)
        if not running:
            if all(s == 'finished' for s in states.values()):
                status = 'complete'
            elif status == 'running':
                status = 'task errors need inspection'
        if time.monotonic() - last_export >= 15 or not running:
            progress = report(root)
            for row in progress['cells']:
                if row['id'] in running:
                    row['state'] = 'running'
            progress.update(status=status, token_budget=budget, tokens_used=spent + sum(token_usage(results.get(k, {})) for k in running),
                            reserved_tokens=reserved, unknown_usage=unknown, archived_reported_tokens=carried,
                            unreported_usage_reserve=missing_reserve, updated_at=time.time())
            write_json(root / 'progress.json', progress)
            export_progress(root, Path(web), progress)
            last_export = time.monotonic()
        if not running:
            break
        time.sleep(3)
    write_json(root / 'stopped.json', {'status': status, 'time': time.time()})
    return progress



def run_pass(fixtures, rom, game_data, output, web, models, *, budget, workers=4, provider_workers=2, resume=False):
    root = Path(output).resolve()
    root.mkdir(parents=True, exist_ok=resume)
    with (root / 'coordinator.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('Another coordinator already owns this pass') from None
        return _run_pass(fixtures, rom, game_data, root, web, models, budget=budget,
                         workers=workers, provider_workers=provider_workers, resume=resume)
