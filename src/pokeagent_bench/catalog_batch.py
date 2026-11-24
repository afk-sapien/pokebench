"""Budgeted catalog execution and compact cross-category result summaries."""
from collections import defaultdict
from pathlib import Path

from .catalog_execution import PROVIDERS, _read, inventory, run_task
from .core import write_json
from .benchmark_tracks import SHORT, LONG, NAMES, for_category, kept, ranked_average, validate
from .evaluation_catalog import retired_tasks, task_definition
from .interrupts import pause_on_interrupt
from .providers import SetupError


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
        if separator != ':' or provider not in PROVIDERS or not name:
            raise ValueError('Models must use codex:MODEL, claude:MODEL or openai-compatible:MODEL')
        parsed.append((provider, name))
    if not parsed or len(set(parsed)) != len(parsed):
        raise ValueError('Supply distinct models')
    cells = []
    for row in available:
        if row['id'] not in selected:
            continue
        if not row['runnable']:
            raise ValueError(f'Task is not runnable: {row["id"]}')
        for provider, model in parsed:
            for variant in row['variants']:
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


def reserved(result):
    """True when the only unknown usage of a finished task is failed calls already charged at their reserve."""
    usage = result.get('usage', {})
    return (type(usage.get('unreported_token_reserve')) is int and usage['unreported_token_reserve'] > 0
            and all(type(usage.get(key)) is int and usage[key] >= 0 for key in ('input_tokens', 'output_tokens')))


def resumable(folder):
    """True when a task stopped by a provider error mid decision can resume from its checkpoint."""
    folder = Path(folder)
    try:
        result, error = _read(folder / 'result.json'), _read(folder / 'error.json')
        phase = _read(folder / 'pending.json').get('phase')
    except (OSError, ValueError, AttributeError):
        return False
    from .recovery import IN_FLIGHT
    return (result.get('stop_reason') == 'provider_error' and error.get('kind') == 'provider_error'
            and phase == IN_FLIGHT and (folder / 'recovery.json').is_file())


def recover(output, rom, guard=None):
    """Finish tasks a pause or a provider error stopped mid task, from their checkpoints.

    A task stopped by a provider error after the model may have run keeps that attempt in provider-error-NN
    and resumes with the failed call charged at its token reserve. Each task resumes at most once per command,
    so a provider that keeps failing cannot loop. Return False after a Ctrl-C pause.
    """
    from .cli import execute, parser
    from .recovery import reopen
    output = Path(output)
    for row in report(output)['cells']:
        folder = output / row['id']
        if not folder.is_dir():
            continue
        if guard and guard.requested:
            return False
        if not any(folder.iterdir()):
            folder.rmdir()
            continue
        try:
            attempt = reopen(rom, folder)
        except ValueError as error:
            if row['state'] not in ('finished', 'evaluation_error'):
                raise
            # This code cannot continue the stopped run exactly, so it stays a failed task.
            print(f'{row["task_id"]} stopped on a provider error and cannot resume here: {error}', flush=True)
            continue
        if attempt is None and row['state'] in ('finished', 'evaluation_error'):
            continue
        if not (folder / 'recovery.json').is_file():
            continue
        if attempt is not None:
            print(f'Resuming {row["task_id"]} from its checkpoint after a provider error. The failed attempt is kept '
                  f'in {attempt}.', flush=True)
        else:
            print(f'Resuming {row["task_id"]} from its checkpoint.', flush=True)
        result = execute(parser().parse_args(['resume', '--rom', str(rom), '--run', str(folder)]))
        if isinstance(result, dict) and result.get('state') == 'paused':
            if guard and guard.requested:
                return False
            raise ValueError(f'{row["task_id"]} paused again after a provider error with no model reply. '
                             'No tokens were spent on it. Run the same command again later')
        if isinstance(result, dict) and result.get('stop_reason') == 'provider_error':
            raise ValueError(f'{row["task_id"]} stopped on a provider error again. Each attempt is kept in its '
                             'folder. Run the same command again later')
    return True


def cell_result(path):
    path = Path(path)
    raw = _read(path / 'result.json') if (path / 'result.json').is_file() else None
    failed = path / 'error.json'
    if failed.is_file():
        error = _read(failed)
        # Error metadata overrides a partial result, but must not erase charges.
        raw = {**(raw or {}), **{key: value for key, value in error.items() if key != 'usage'},
               'usage': (raw or {}).get('usage', error.get('usage', {}))}
    return raw


def report(batch):
    batch = Path(batch)
    manifest = _read(batch / 'plan.json')
    models = defaultdict(list)
    rows = []
    for cell in kept(manifest['cells']):
        raw = cell_result(batch / cell['id'])
        benchmark = for_category(cell['category'])
        row = {**cell, 'benchmark': benchmark, 'state': 'pending', 'value': None, 'tokens': 0}
        if raw is not None:
            row['tokens'] = token_usage(raw)
            row['decisions'] = raw.get('usage', {}).get('calls')
            row['controller_actions'] = raw.get('actions')
            row['accounting_complete'] = accounting_complete(raw)
            row['provider_errors'] = len(raw.get('provider_errors') or [])
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
    retired = retired_tasks()
    for (benchmark, provider, model), values in models.items():
        by_task = defaultdict(list)
        for row in values:
            if row['value'] is not None and row['task_id'] not in retired:
                by_task[(row['category'], row.get('score_group', row['task_id']))].append(row['value'])
        categories = defaultdict(list)
        for (category, _), scores in by_task.items():
            categories[category].append(sum(scores) / len(scores))
        category_scores = {key: sum(scores) / len(scores) for key, scores in categories.items()}
        ranked = benchmark == SHORT
        summaries.append({'benchmark': benchmark, 'name': NAMES[benchmark], 'provider': provider, 'model': model,
                          'completed': sum(row['state'] == 'finished' for row in values),
                          'planned': len(values), 'evaluation_errors': sum(row['state'] == 'evaluation_error' for row in values),
                          'tokens': sum(row['tokens'] for row in values),
                          'accounting_complete': all(row.get('accounting_complete', True) for row in values),
                          'category_scores': category_scores if ranked else {},
                          'available_category_average': ranked_average(category_scores) if ranked else None})
        if benchmark == LONG:
            finished = [row for row in values if row['state'] == 'finished']
            summaries[-1]['campaign_mean_progress'] = sum(row['value'] for row in finished) / len(finished) if finished else None
            summaries[-1]['champion_completions'] = sum(row.get('campaign', {}).get('champion', False) for row in finished)
            summaries[-1]['campaign_runs'] = [{key: row.get(key) for key in ('id', 'state', 'campaign', 'tokens', 'accounting_complete')} for row in values]
    return {'protocol': manifest['protocol'], 'benchmark': manifest.get('benchmark'),
            'benchmarks': sorted({row['benchmark'] for row in rows}), 'models': summaries, 'cells': rows,
            'note': 'Available results only. Equal task-family weights within categories. Inventory variants share their parent task weight. The PokeBench average covers navigation, battle, operations and objectives. Stored preparation attempts are not read. Retired tasks are not scored. PokeBench reports focused-task performance. PokeBench Long reports campaign progress and Champion completion separately. Milestone tasks score the share of their ordered milestones reached, from 0 to 1. These scores are never averaged together. Check coverage before comparing averages.'}


def run_batch(fixtures, rom, game_data, output, *, models=None, tasks=None, repeats=1,
              budget=None, resume=False, benchmark=None, on_cell=None):
    """Run each planned cell in order, each bounded only by its own decision and token caps.

    Run order must never change what a task is allowed, so the budget is a reported reference.
    It never stops or shortens a task. The worst case is the sum of the planned token caps.
    """
    if budget is not None and (type(budget) is not int or budget <= 0):
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
    with pause_on_interrupt() as guard:
        # Paused tasks and tasks a provider error stopped mid decision resume from their checkpoints first.
        recovered = recover(output, rom, guard) if resume else True
        current_report = report(output)
        write_json(output / 'report.json', current_report)
        # Check every existing cell before any new paid work, including later cells.
        # Any other failed cell is never run again, so its unknown usage stays reported without blocking later tasks.
        for row in current_report['cells']:
            destination = output / row['id']
            if not destination.exists() or not recovered:
                continue
            if row['state'] not in ('finished', 'evaluation_error'):
                raise ValueError(f'Unfinished cell needs recovery before resume: {row["id"]} ({row["state"]}). '
                                 'Resume its saved session first')
            if (row['state'] == 'finished' and not row.get('accounting_complete', False)
                    and not reserved(cell_result(destination))):
                raise ValueError(f'Uncertain token usage needs reconciliation before resume: {row["id"]}')
        used = sum(row['tokens'] for row in current_report['cells'])
        failed_in_row = 0
        for cell in kept(manifest['cells']) if recovered else ():
            destination = output / cell['id']
            if cell_result(destination) is not None:
                continue
            # Ctrl-C between tasks stops here, before the next task starts.
            if guard and guard.requested:
                break
            from .catalog_execution import select_scenario
            current = _read(select_scenario(fixtures, cell['task_id'], cell['variant']) / 'scenario.json')
            if current['state_sha256'] != cell['fixture_sha256'] or current['catalog_sha256'] != cell['evaluation_spec_sha256']:
                raise ValueError('A planned starting state or task specification changed')
            try:
                run_task(fixtures, cell['task_id'], rom, game_data, destination,
                         provider=cell['provider'], model=cell['model'], variant=cell['variant'], token_limit=cell['token_limit'],
                         decision_limit=cell.get('decision_limit'), reasoning_effort=cell.get('reasoning_effort', 'low'),
                         run_limits=cell.get('run_limits'))
            except SetupError:
                # Local setup stopped the task before it started, so nothing ran or was spent.
                # The task stays pending and the same command starts it once the setup is fixed.
                raise
            except (ValueError, OSError, RuntimeError) as error:
                destination.mkdir(parents=True, exist_ok=True)
                existing = cell_result(destination)
                write_json(destination / 'error.json', {'evaluation_error': str(error),
                    'usage': existing.get('usage', {}) if existing else {'accounting_complete': False}})
                used += token_usage(cell_result(destination))
                latest = report(output)
                write_json(output / 'report.json', latest)
                if on_cell:
                    on_cell(next(row for row in latest['cells'] if row['id'] == cell['id']))
                # The failed cell is never retried automatically, so unknown usage cannot loop.
                # Two failures in a row point at the setup rather than one task, so the batch stops.
                failed_in_row += 1
                if failed_in_row >= 2:
                    raise
                continue
            failed_in_row = 0
            value = cell_result(destination)
            if value is None:
                raise ValueError('Task did not persist a final result')
            used += token_usage(value)
            latest = report(output)
            write_json(output / 'report.json', latest)
            if on_cell:
                on_cell(next(row for row in latest['cells'] if row['id'] == cell['id']))
            # A cell paused by a provider error or Ctrl-C waits for a rerun before any later cell starts.
            if not accounting_complete(value) or value.get('state') == 'paused':
                break
    result = report(output)
    result.update(token_budget=budget, tokens_used=used,
                  worst_case_tokens=sum(cell['token_limit'] for cell in kept(manifest['cells'])))
    write_json(output / 'report.json', result)
    return result
