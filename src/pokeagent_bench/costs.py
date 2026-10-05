"""Normalized Standard Codex credit estimates from recorded usage, never invoices."""
import json
from functools import lru_cache
from pathlib import Path

RATE_CARD = {
    'id': 'codex-standard-2026-10-03',
    'as_of': '2026-10-03',
    'source': 'https://learn.chatgpt.com/docs/pricing',
    'unit': 'credits_per_million_tokens',
    'basis': 'Standard speed equivalent, not actual subscription charges or quota',
    'rates': {
        'gpt-6-astra': [250, 25, 1250],
        'gpt-6-sol': [50, 5, 250],
        'gpt-6-luna': [2.5, 0.25, 12.5],
        'gpt-5.6-sol': [100, 10, 500],
        'gpt-5.6-terra': [50, 5, 300],
        'gpt-5.6-luna': [5, 0.5, 30],
        'gpt-5.5': [125, 12.5, 750],
    },
    'rate_order': ['uncached_input', 'cached_input', 'output'],
}


def estimate(model, usage):
    rates = RATE_CARD['rates'].get(model)
    keys = ('input_tokens', 'cached_input_tokens', 'output_tokens')
    if not rates or any(type(usage.get(k)) is not int or usage[k] < 0 for k in keys):
        return None
    inputs, cached, outputs = (usage[k] for k in keys)
    if cached > inputs:
        return None
    return ((inputs - cached) * rates[0] + cached * rates[1] + outputs * rates[2]) / 1_000_000


@lru_cache(maxsize=1024)
def _read_usage(path, size, modified):
    totals = dict(input_tokens=0, cached_input_tokens=0, output_tokens=0)
    calls = 0
    try:
        with Path(path).open() as stream:
            for line in stream:
                usage = json.loads(line)['usage']
                if any(type(usage.get(k)) is not int or usage[k] < 0 for k in totals):
                    return None
                if usage['cached_input_tokens'] > usage['input_tokens']:
                    return None
                for key in totals:
                    totals[key] += usage[key]
                calls += 1
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return {**totals, 'calls': calls}


def enrich(attempt, run):
    """Validate complete saved usage and leave unknown amounts unknown."""
    attempt.update(estimated_credits=None, cost_complete=False, cost_rate_card=RATE_CARD['id'])
    run = Path(run)
    try:
        result = json.loads((run/'result.json').read_text())
        log = run/'decisions.jsonl'
        stat = log.stat()
    except (OSError, ValueError):
        attempt['cost_note'] = 'Usage records unavailable'
        return
    totals = _read_usage(str(log.resolve()), stat.st_size, stat.st_mtime_ns)
    usage = result.get('usage', {})
    if totals is None:
        attempt['cost_note'] = 'Detailed cache usage unavailable'
        return
    attempt.update({key: totals[key] for key in ('input_tokens', 'cached_input_tokens', 'output_tokens')})
    consistent = all(totals[k] == usage.get(k) for k in ('input_tokens', 'output_tokens', 'calls'))
    interrupted = bool(attempt.get('prior_interruptions'))
    cost = estimate(attempt['model'], totals)
    complete = (consistent and usage.get('accounting_complete') is True
                and attempt['status'] == 'finished' and not interrupted and cost is not None)
    attempt['estimated_credits'] = cost
    attempt['cost_complete'] = complete
    attempt['cost_note'] = ('Complete Standard-rate estimate' if complete else
                            'Partial or unknown usage, excluded from cost ranking')


def efficiency(attempts, models, shared):
    """Task macro averages include failures and require shared complete cost coverage."""
    eligible = [task for task in shared if all(
        (group := [a for a in attempts if a['task'] == task and a['model'] == model])
        and all(a.get('cost_complete') and a.get('estimated_credits') is not None for a in group)
        for model in models)]
    rows = []
    for model in models:
        costs, passes = [], []
        for task in eligible:
            group = [a for a in attempts if a['model'] == model and a['task'] == task]
            costs.append(sum(a['estimated_credits'] for a in group) / len(group))
            passes.append(sum(bool(a['completed']) for a in group) / len(group))
        rows.append({
            'model': model,
            'cost_scored_tasks': len(eligible),
            'cost_success_rate': 100 * sum(passes) / len(passes) if passes else None,
            'credits_per_attempt': sum(costs) / len(costs) if costs else None,
            'credits_per_success': sum(costs) / sum(passes) if sum(passes) else None,
        })
    return {'task_ids': eligible, 'models': rows, 'rate_card': RATE_CARD,
            'policy': 'Equal task weights. Includes failed attempts. Unknown usage excluded for every model.'}
