"""Budgeted catalog execution and compact cross-category result summaries."""
from collections import defaultdict
from pathlib import Path

from .catalog_execution import _read, inventory, run_task
from .core import write_json
from .benchmark_tracks import SHORT, LONG, NAMES, for_category, validate
from .evaluation_catalog import task_definition


def plan(fixtures, models, tasks=None, repeats=1, *, benchmark=SHORT):
    validate(benchmark)
    if type(repeats) is not int or repeats < 1:
        raise ValueError('Repeats must be a positive integer')
    available = [row for row in inventory(fixtures)['tasks'] if for_category(row['category']) == benchmark]
    selected = set(tasks or [row['id'] for row in available])
    unknown = selected - {row['id'] for row in available}
    if unknown:
        raise ValueError('Tasks are not in ' + NAMES[benchmark] + ': ' + ', '.join(sorted(unknown)) + '. Select the matching --benchmark')
    parsed = []
    for model in models:
        provider, separator, name = model.partition(':')
        if separator != ':' or provider not in ('codex', 'claude') or not name:
            raise ValueError('Models must use codex:MODEL or claude:MODEL')
        parsed.append((provider, name))
    if not parsed or len(set(parsed)) != len(parsed):
        raise ValueError('Supply distinct models')
    cells = []
    for row in available:
        if row['id'] not in selected:
            continue
        if not row['runnable']:
            raise ValueError(f'Task is not runnable: {row["id"]}')
        # Preparation opponent variants are assessed within the frozen submission.
        variants = row['variants'] if row['mode'] != 'preparation' else row['variants'][:1]
        for provider, model in parsed:
            for variant in variants:
                for repeat in range(repeats):
                    fixture = _read(Path(variant['path']) / 'scenario.json')
                    cells.append({'fixture_sha256': fixture['state_sha256'],
                                  'evaluation_spec_sha256': fixture['catalog_sha256'],
                                  'id': f'cell-{len(cells)+1:04d}', 'task_id': row['id'],
                                  'category': row['category'], 'mode': row['mode'], 'benchmark': benchmark,
                                  'score_group': task_definition(row['id']).get('variant_of', row['id']),
                                  'provider': provider, 'model': model, 'variant': variant['variant'],
                                  'repeat': repeat + 1, 'token_limit': task_definition(row['id'])['token_limit'],
                                  'decision_limit': task_definition(row['id']).get('decision_limit', 10000)})
    return {'protocol': 'catalog-batch-v3-decisions', 'benchmark': benchmark, 'cells': cells, 'cell_count': len(cells)}


def token_usage(result):
    usage = result.get('usage', {})
    return sum(value for key in ('input_tokens', 'output_tokens')
               if type(value := usage.get(key)) is int and value >= 0)


def accounting_complete(result):
    usage = result.get('usage', {})
    return usage.get('accounting_complete', True) is True and all(
        type(usage.get(key)) is int and usage[key] >= 0
        for key in ('input_tokens', 'output_tokens'))


def cell_result(path):
    path = Path(path)
    raw = None
    for name in ('preparation-result.json', 'result.json', 'preparation/result.json'):
        source = path / name
        if source.is_file():
            raw = _read(source)
            break
    reassessment = path / 'reassessment.json'
    if raw is not None and reassessment.is_file():
        update = _read(reassessment)
        assessment = update['assessment']
        if not raw.get('submitted') or assessment.get('submission_sha256') != raw.get('submission_sha256'):
            raise ValueError('Reassessment must use the original frozen submission')
        if assessment.get('evaluation_errors') or assessment.get('model_calls') != 0:
            raise ValueError('Reassessment must finish without errors or model calls')
        raw = {**raw, 'assessment': assessment, 'reassessment': {k: v for k, v in update.items() if k != 'assessment'}}
    failed = path / 'error.json'
    if failed.is_file():
        error = _read(failed)
        # Error metadata overrides a partial result, but must not erase charges.
        raw = {**(raw or {}), **{key: value for key, value in error.items() if key != 'usage'},
               'usage': (raw or {}).get('usage', error.get('usage', {}))}
    if raw is None:
        return None
    if raw.get('reason') == 'preparation_error':
        raw['evaluation_error'] = raw.get('error') or 'Preparation runtime failed'
        # Historical preparation errors recorded zero even when usage was unknown.
        raw['usage'] = {**raw.get('usage', {})}
        raw['usage'].setdefault('accounting_complete', False)
    usage_path = path / 'model-usage.json'
    if usage_path.is_file():
        raw['usage'] = _read(usage_path)
    return raw


def report(batch):
    batch = Path(batch)
    manifest = _read(batch / 'plan.json')
    models = defaultdict(list)
    rows = []
    for cell in manifest['cells']:
        raw = cell_result(batch / cell['id'])
        benchmark = for_category(cell['category'])
        row = {**cell, 'benchmark': benchmark, 'state': 'pending', 'value': None, 'tokens': 0}
        if raw is not None:
            row['tokens'] = token_usage(raw)
            row['decisions'] = raw.get('usage', {}).get('calls')
            row['controller_actions'] = raw.get('actions')
            row['accounting_complete'] = accounting_complete(raw)
            if cell['mode'] == 'preparation':
                assessment = raw.get('assessment') or {}
                if raw.get('evaluation_error') or assessment.get('evaluation_errors'):
                    row['state'] = 'evaluation_error'
                elif raw.get('state') in ('running', 'paused', 'interrupted'):
                    row['state'] = raw['state']
                elif raw.get('submitted') and assessment.get('win_rate') is not None:
                    row.update(state='finished', value=assessment['win_rate'])
                elif raw.get('submitted') or raw.get('stop_reason') == 'submitted':
                    row['state'] = 'assessment_pending'
                else:
                    row.update(state='finished', value=0)
                row['assessment'] = assessment
            else:
                if raw.get('evaluation_error') or raw.get('outcome_category') in ('infrastructure_failure', 'interface_failure'):
                    row['state'] = 'evaluation_error'
                elif raw.get('state') == 'finished':
                    value = raw.get('score', 0) / raw.get('score_max', 1)
                    row.update(state='finished', value=value)
                else:
                    row['state'] = raw.get('state', 'pending')
            row['stop_reason'] = raw.get('stop_reason', raw.get('reason'))
            if benchmark == LONG:
                row['campaign'] = {'points': raw.get('score', 0), 'maximum_points': raw.get('score_max', 1000),
                    'champion': raw.get('completed', False), 'milestones': len(raw.get('achievements', [])),
                    'frames': raw.get('frames'), 'wall_seconds': raw.get('wall_seconds')}
        models[(benchmark, cell['provider'], cell['model'])].append(row)
        rows.append(row)
    summaries = []
    for (benchmark, provider, model), values in models.items():
        by_task = defaultdict(list)
        for row in values:
            if row['value'] is not None:
                by_task[(row['category'], row.get('score_group', row['task_id']))].append(row['value'])
        categories = defaultdict(list)
        for (category, _), scores in by_task.items():
            categories[category].append(sum(scores) / len(scores))
        category_scores = {key: sum(scores) / len(scores) for key, scores in categories.items()}
        summaries.append({'benchmark': benchmark, 'name': NAMES[benchmark], 'provider': provider, 'model': model,
                          'completed': sum(row['state'] == 'finished' for row in values),
                          'planned': len(values), 'evaluation_errors': sum(row['state'] == 'evaluation_error' for row in values),
                          'tokens': sum(row['tokens'] for row in values),
                          'accounting_complete': all(row.get('accounting_complete', True) for row in values),
                          'category_scores': category_scores if benchmark == SHORT else {},
                          'available_category_average': sum(category_scores.values()) / len(category_scores) if category_scores and benchmark == SHORT else None})
        if benchmark == LONG:
            finished = [row for row in values if row['state'] == 'finished']
            summaries[-1]['campaign_mean_progress'] = sum(row['value'] for row in finished) / len(finished) if finished else None
            summaries[-1]['champion_completions'] = sum(row.get('campaign', {}).get('champion', False) for row in finished)
            summaries[-1]['campaign_runs'] = [{key: row.get(key) for key in ('id', 'state', 'campaign', 'tokens', 'accounting_complete')} for row in values]
    return {'protocol': manifest['protocol'], 'benchmark': manifest.get('benchmark'),
            'benchmarks': sorted({row['benchmark'] for row in rows}), 'models': summaries, 'cells': rows,
            'note': 'Available results only. Equal task-family weights within categories. Inventory variants share their parent task weight. PokeBench reports focused-task performance. PokeBench Long reports campaign progress and Champion completion separately. These scores are never averaged together. Check coverage before comparing averages.'}


def run_batch(fixtures, rom, game_data, output, *, models=None, tasks=None, repeats=1,
              budget, resume=False, benchmark=None):
    if type(budget) is not int or budget <= 0:
        raise ValueError('Batch token budget must be a positive integer')
    output = Path(output)
    if resume:
        manifest = _read(output / 'plan.json')
        if benchmark is not None:
            validate(benchmark)
            if any(for_category(cell['category']) != benchmark for cell in manifest['cells']):
                raise ValueError('Saved batch belongs to a different benchmark')
    else:
        manifest = plan(fixtures, models or [], tasks, repeats, benchmark=benchmark or SHORT)
        output.mkdir(parents=True, exist_ok=False)
        write_json(output / 'plan.json', manifest)
    current_report = report(output)
    write_json(output / 'report.json', current_report)
    # Check every existing cell before any new paid work, including later cells.
    for row in current_report['cells']:
        destination = output / row['id']
        if not destination.exists():
            continue
        if row['state'] not in ('finished', 'evaluation_error'):
            raise ValueError(f'Unfinished cell needs recovery before resume: {row["id"]} ({row["state"]}). '
                             'Resume its saved session or finish its assessment first')
        if not row.get('accounting_complete', False):
            raise ValueError(f'Uncertain token usage needs reconciliation before resume: {row["id"]}')
    used = sum(row['tokens'] for row in current_report['cells'])
    for cell in manifest['cells']:
        destination = output / cell['id']
        if cell_result(destination) is not None:
            continue
        if used >= budget:
            break
        from .catalog_execution import select_scenario
        current = _read(select_scenario(fixtures, cell['task_id'], cell['variant']) / 'scenario.json')
        if current['state_sha256'] != cell['fixture_sha256'] or current['catalog_sha256'] != cell['evaluation_spec_sha256']:
            raise ValueError('A planned starting state or task specification changed')
        allowance = min(cell['token_limit'], budget - used)
        if allowance < min(cell['token_limit'], 10000):
            break
        try:
            run_task(fixtures, cell['task_id'], rom, game_data, destination,
                     provider=cell['provider'], model=cell['model'], variant=cell['variant'], token_limit=allowance,
                     decision_limit=cell.get('decision_limit'))
        except (ValueError, OSError, RuntimeError) as error:
            destination.mkdir(parents=True, exist_ok=True)
            existing = cell_result(destination)
            write_json(destination / 'error.json', {'evaluation_error': str(error),
                'usage': existing.get('usage', {}) if existing else {'accounting_complete': False}})
            write_json(output / 'report.json', report(output))
            # Unknown usage must not produce an unlimited automatic retry loop.
            raise
        value = cell_result(destination)
        if value is None:
            raise ValueError('Task did not persist a final result')
        used += token_usage(value)
        write_json(output / 'report.json', report(output))
        if not accounting_complete(value):
            break
    result = report(output)
    result.update(token_budget=budget, tokens_used=used)
    write_json(output / 'report.json', result)
    return result
