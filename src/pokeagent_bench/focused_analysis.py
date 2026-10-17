"""Local focused-pass analysis, with repeats kept separate from the main score."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import shutil

from .catalog_batch import report
from .evaluation_catalog import task_definition

CATEGORIES = ('navigation', 'battle', 'operations', 'preparation', 'objectives')
LABELS = {'gpt-5.6-sol': 'Sol', 'gpt-5.6-terra': 'Terra', 'gpt-5.6-luna': 'Luna',
          'claude-opus-5-5': 'Opus', 'claude-sonnet-5-5': 'Sonnet', 'claude-haiku-5-5': 'Haiku'}


def grouped_scores(cells):
    """Average starts within score groups, groups within categories, then categories."""
    groups = defaultdict(list)
    for row in cells:
        if row['state'] == 'finished' and row.get('value') is not None:
            groups[(row['category'], row.get('score_group', row['task_id']))].append(row['value'])
    categories = defaultdict(list)
    for (category, _), values in groups.items():
        categories[category].append(sum(values) / len(values))
    scores = {key: sum(values) / len(values) for key, values in categories.items()}
    return scores, sum(scores.values()) / len(scores) if scores else None


def task_sensitivity(cells):
    """Descriptive rank range after removing each score group once, not an interval."""
    models = sorted({c['model'] for c in cells})
    groups = {c.get('score_group', c['task_id']) for c in cells}
    ranks = defaultdict(list)
    for group in sorted(groups):
        scores = {model: grouped_scores([c for c in cells if c['model'] == model
                                        and c.get('score_group', c['task_id']) != group])[1]
                  for model in models}
        if any(value is None for value in scores.values()):
            continue
        for model, value in scores.items():
            ranks[model].append(1 + sum(other > value + 1e-12 for other in scores.values()))
    return {'omissions': len(groups), 'rows': [
        {'model': model, 'best_rank': min(values), 'worst_rank': max(values)}
        for model, values in ranks.items()]}


def trace_audit(path):
    """Count observable interface symptoms without claiming they prove a core bug."""
    count = errors = idle = 0
    locations = Counter()
    last = None
    source = path / 'decisions.jsonl'
    if source.exists():
        with source.open() as stream:
            for line in stream:
                row = json.loads(line)
                count += 1
                decision = row.get('decision', {})
                errors += bool(decision.get('interface_error'))
                idle += not decision.get('actions') and not decision.get('look_back')
                game = row.get('provider', {}).get('context', {}).get('game', {})
                location = game.get('location') or {}
                if location.get('map_name'):
                    last = location['map_name']
                    locations[last] += 1
    return {'recorded_decisions': count, 'format_error_decisions': errors,
            'no_action_decisions': idle, 'last_map': last,
            'most_observed_map': locations.most_common(1)[0][0] if locations else None,
            'most_observed_map_decisions': locations.most_common(1)[0][1] if locations else 0}


def repeat_summary(original, repeats):
    selected = {r['task_id'] for r in repeats}
    rows = []
    for model in sorted({r['model'] for r in original}):
        for task in sorted(selected):
            before = [r for r in original if r['model'] == model and r['task_id'] == task]
            after = [r for r in repeats if r['model'] == model and r['task_id'] == task]
            complete = [r for r in before + after if r['state'] == 'finished' and r.get('value') is not None]
            rows.append({'model': model, 'task_id': task,
                         'initial': before[0]['value'] if before else None,
                         'repeats': [{'repeat': r['repeat'], 'state': r['state'], 'value': r.get('value'), 'replay': r.get('replay')} for r in after],
                         'mean': sum(r['value'] for r in complete) / len(complete) if complete else None,
                         'completed': len(complete), 'planned': len(before + after),
                         'changed': bool(before and any(r['state'] == 'finished' and r.get('value') != before[0]['value'] for r in after))})
    return rows


def collect(root, web, prefix='', audit=True):
    data = report(root)
    progress_path = root / 'progress.json'
    progress = json.loads(progress_path.read_text()) if progress_path.exists() else {}
    live = {row['id']: row['state'] for row in progress.get('cells', [])}
    fields = ('id', 'task_id', 'category', 'score_group', 'model', 'provider', 'variant', 'repeat',
              'mode', 'state', 'value', 'tokens', 'decisions', 'controller_actions', 'stop_reason',
              'decision_limit', 'token_limit', 'accounting_complete', 'fixture_sha256', 'evaluation_spec_sha256')
    cache_path = root / 'trace-audit-v060.json'
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    output = []
    for row in data['cells']:
        clean = {k: row[k] for k in fields if k in row}
        manifest_path = root / row['id'] / 'manifest.json'
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text())
            agent = manifest.get('agent', {})
            configuration = agent.get('configuration', {})
            clean['runtime'] = {
                'benchmark': manifest.get('benchmark'),
                'action_policy': manifest.get('action_policy'),
                'core_version': manifest.get('core', {}).get('version'),
                'core_source_sha256': manifest.get('core', {}).get('source_sha256'),
                'manifest_sha256': sha256(manifest_path.read_bytes()).hexdigest(),
                'reasoning_effort': agent.get('reasoning_effort'),
                **{key: configuration.get(key) for key in
                   ('context_turns', 'compact_at', 'presentation', 'controller_timing', 'observation_policy')}}
        if row['state'] == 'pending' and live.get(row['id']) == 'running':
            clean['state'] = 'running'
        revision = row.get('attempt_revision') or ('v057' if row.get('replacement_condition') else 'v056')
        replay = Path('replays') / f"focused-{revision}-{row['id']}.html"
        clean['replay'] = prefix + str(replay) if (web / replay).is_file() else None
        if row['mode'] == 'preparation':
            assessment = row.get('assessment', {})
            clean['preparation'] = {k: assessment[k] for k in ('wins', 'trials', 'win_rate', 'model_calls', 'policy_version', 'policy_sha256') if k in assessment}
        if audit:
            trace = root / row['id'] / 'decisions.jsonl'
            fingerprint = [trace.stat().st_size, trace.stat().st_mtime_ns] if trace.exists() else None
            cached = cache.get(row['id'], {})
            if cached.get('fingerprint') != fingerprint or 'value' not in cached:
                cached = {'fingerprint': fingerprint, 'value': trace_audit(root / row['id'])}
                cache[row['id']] = cached
            clean['audit'] = cached['value']
        output.append(clean)
    if audit:
        cache_path.write_text(json.dumps(cache, indent=2) + '\n')
    return output, progress


def build_analysis(root, web, repeat_root=None):
    root, web = Path(root), Path(web)
    cells, progress = collect(root, web)
    models = []
    for name in sorted({c['model'] for c in cells}):
        rows = [c for c in cells if c['model'] == name]
        categories, score = grouped_scores(rows)
        models.append({'model': name, 'label': LABELS.get(name, name), 'score': score,
                       'categories': categories, 'finished': sum(c['state'] == 'finished' for c in rows),
                       'planned': len(rows), 'tokens': sum(c['tokens'] for c in rows),
                       'evaluation_errors': sum(c['state'] == 'evaluation_error' for c in rows),
                       'format_error_decisions': sum(c['audit']['format_error_decisions'] for c in rows)})
    models.sort(key=lambda x: -(x['score'] if x['score'] is not None else -1))
    tasks = []
    for task in sorted({c['task_id'] for c in cells}, key=lambda t: (CATEGORIES.index(next(c['category'] for c in cells if c['task_id'] == t)), t)):
        rows = [c for c in cells if c['task_id'] == task]
        definition = task_definition(task)
        values = [c['value'] for c in rows if c['state'] == 'finished' and c.get('value') is not None]
        tasks.append({'id': task, 'title': definition['title'], 'category': rows[0]['category'],
                      'goal': definition.get('agent_goal') or (definition.get('objective') or {}).get('description', definition['title']),
                      'start': definition.get('start', ''), 'action_policy': definition.get('action_policy'),
                      'mode': rows[0]['mode'], 'decision_limit': rows[0]['decision_limit'],
                      'token_limit': rows[0]['token_limit'], 'all_full_score': len(values) == len(rows) and all(v == 1 for v in values),
                      'all_zero': len(values) == len(rows) and all(v == 0 for v in values)})
    repeat_cells, repeat_progress = ([], {})
    if repeat_root and (Path(repeat_root) / 'plan.json').exists():
        repeat_cells, repeat_progress = collect(Path(repeat_root), web / 'stability-v060', 'stability-v060/', audit=False)
    reasons = Counter(c.get('stop_reason') or ('preparation_assessed' if c['mode'] == 'preparation' else 'unspecified') for c in cells)
    return {'schema': 'focused-analysis-v060', 'generated_at': datetime.now(timezone.utc).isoformat(),
            'source_plan_sha256': sha256((root / 'plan.json').read_bytes()).hexdigest(),
            'models': models, 'tasks': tasks, 'cells': cells, 'categories': list(CATEGORIES),
            'task_sensitivity': task_sensitivity(cells),
            'counts': {'tasks': len(tasks), 'score_groups': len({c['score_group'] for c in cells}),
                       'starts': len(cells) // len(models), 'models': len(models), 'attempts': len(cells),
                       'finished': sum(c['state'] == 'finished' for c in cells),
                       'evaluation_errors': sum(c['state'] == 'evaluation_error' for c in cells),
                       'all_full_score_tasks': sum(t['all_full_score'] for t in tasks),
                       'all_zero_tasks': sum(t['all_zero'] for t in tasks)},
            'usage': {'selected_tokens': sum(c['tokens'] for c in cells),
                      'reported_tokens': progress.get('tokens_used', sum(c['tokens'] for c in cells)),
                      'archived_tokens': progress.get('archived_reported_tokens', 0),
                      'unknown_reserve': progress.get('unreported_usage_reserve', 0), 'combined_ceiling': 552000000},
            'conditions': {key: dict(Counter(str(c['runtime'].get(key)) for c in cells if c.get('runtime')))
                           for key in ('benchmark', 'action_policy', 'core_version', 'reasoning_effort',
                                       'context_turns', 'compact_at', 'presentation', 'controller_timing', 'observation_policy')},
            'audit': {'stop_reasons': dict(reasons),
                      'format_error_decisions': sum(c['audit']['format_error_decisions'] for c in cells),
                      'runs_with_format_errors': sum(c['audit']['format_error_decisions'] > 0 for c in cells),
                      'trace_decisions': sum(c['audit']['recorded_decisions'] for c in cells)},
            'repeats': {'rows': repeat_summary(cells, repeat_cells), 'cells': repeat_cells,
                        'status': repeat_progress.get('status', 'not started'),
                        'finished': sum(c['state'] == 'finished' for c in repeat_cells), 'planned': len(repeat_cells),
                        'reported_tokens': repeat_progress.get('tokens_used', 0),
                        'unknown_reserve': repeat_progress.get('unreported_usage_reserve', 0),
                        'token_ceiling': repeat_progress.get('token_budget', 105000000)}}


def export(root, web, repeat_root=None, paper_input=None):
    web = Path(web)
    web.mkdir(parents=True, exist_ok=True)
    data = build_analysis(root, web, repeat_root)
    payload = json.dumps(data, indent=2, ensure_ascii=False) + '\n'
    (web / 'focused-analysis.json').write_text(payload)
    if paper_input:
        Path(paper_input).write_text(payload)
    if (web / 'index.html').exists() and not (web / 'historical-index.html').exists():
        shutil.copy2(web / 'index.html', web / 'historical-index.html')
    from .focused_portal import page
    temporary = web / 'index.html.tmp'
    temporary.write_text(page(data))
    temporary.replace(web / 'index.html')
    return data
