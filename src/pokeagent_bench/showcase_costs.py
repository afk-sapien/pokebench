"""API-equivalent cost ranges for the exploratory showcase, never invoices."""
from collections import defaultdict
from functools import lru_cache
import json
from pathlib import Path

from .focused_analysis import grouped_scores

PRICING = {
    'id': 'api-standard-2026-10-15', 'as_of': '2026-10-15', 'currency': 'USD',
    'rate_order': ['input', 'cache_read', 'output', 'cache_write_5m', 'cache_write_1h'],
    'rates': {
        'gpt-6-astra': [10, 1, 50, 12.5, 12.5],
        'gpt-5.6-sol': [4, .4, 20, 5, 5],
        'gpt-5.6-terra': [2, .2, 12, 2.5, 2.5],
        'gpt-5.6-luna': [.2, .02, 1.2, .25, .25],
        'claude-opus-5-5': [4, .2, 20, 5, 8],
        'claude-sonnet-5-5': [2, .1, 10, 2.5, 4],
        'claude-haiku-5-5': [.1, .01, .5, .125, .2],
        'claude-fable-5-1': [10, .25, 50, 12.5, 20],
    },
    'sources': [
        'https://developers.openai.com/api/docs/pricing',
        'https://developers.openai.com/api/docs/models/gpt-5.6-terra',
        'https://developers.openai.com/api/docs/models/gpt-5.6-luna',
        'https://platform.claude.com/docs/en/models/opus-5-5/whats-new-opus-5-5',
        'https://platform.claude.com/docs/en/models/sonnet-5-5/overview',
        'https://platform.claude.com/docs/en/models/haiku-5-5/overview',
        'https://platform.claude.com/docs/en/models/fable-5-1/overview',
    ],
    'basis': 'Standard API-equivalent USD at this dated rate card. Not subscription charges.',
    'range': 'Recorded cache reads are discounted. Unknown cache writes span no write to all uncached input for OpenAI, and 5-minute to 1-hour writes for Claude. Missing cache breakdown spans compatible input prices. These are pricing scenarios, not statistical confidence intervals.',
}


def price_usage(model, usage):
    rates = PRICING['rates'].get(model)
    if rates is None:
        return None
    inputs, outputs = usage.get('input_tokens'), usage.get('output_tokens')
    if any(type(n) is not int or n < 0 for n in (inputs, outputs)):
        return None
    inp, read, out, write, hour = rates
    if model == 'claude-haiku-5-5' and inputs > 100000:
        inp, read, out, write, hour = (n * 5 for n in rates)
    elif model.startswith('gpt-') and inputs > 272000:
        inp, read, write, hour = (n * 2 for n in (inp, read, write, hour))
        out *= 1.5
    cached = usage.get('cached_input_tokens')
    if cached is None:
        return {'low': (inputs * read + outputs * out) / 1e6,
                'high': (inputs * hour + outputs * out) / 1e6}
    if type(cached) is not int or not 0 <= cached <= inputs:
        return None
    creation = usage.get('cache_creation_input_tokens')
    remaining = inputs - cached
    if creation is None:
        low_input, high_input = remaining * inp, remaining * hour
    elif type(creation) is int and 0 <= creation <= remaining:
        low_input = (remaining - creation) * inp + creation * write
        high_input = (remaining - creation) * inp + creation * hour
    else:
        return None
    common = cached * read + outputs * out
    return {'low': (common + low_input) / 1e6, 'high': (common + high_input) / 1e6}


@lru_cache(maxsize=1024)
def read_decisions(path, size, modified, model):
    low = high = 0.0
    inputs = outputs = calls = cached = 0
    try:
        with Path(path).open() as stream:
            for line in stream:
                usage = json.loads(line).get('usage', {})
                cost = price_usage(model, usage)
                if cost is None:
                    continue
                inputs += usage['input_tokens']
                outputs += usage['output_tokens']
                cached += usage.get('cached_input_tokens', 0) or 0
                calls += 1
                low += cost['low']
                high += cost['high']
    except (OSError, ValueError, TypeError):
        return None
    return {'low': low, 'high': high, 'inputs': inputs, 'outputs': outputs, 'calls': calls, 'cached': cached}


def run_cost(root, model, expected_tokens=None):
    root = Path(root)
    empty = {'low': None, 'high': None, 'partial': True, 'note': 'Usage or price unavailable'}
    if model not in PRICING['rates']:
        return empty
    try:
        prep = (root / 'model-usage.json').exists()
        result = json.loads((root / ('model-usage.json' if prep else 'result.json')).read_text())
        usage = result if prep else result['usage']
        total = usage['input_tokens'] + usage['output_tokens']
        if expected_tokens is not None and total != expected_tokens:
            return dict(empty, note='Saved result and displayed attempt differ')
        if prep:
            cost = price_usage(model, usage)
            if cost is None:
                return empty
            return {**cost, 'partial': not usage.get('accounting_complete', False),
                    'note': 'Recorded preparation request', 'recorded_tokens': total,
                    'unreported_token_reserve': usage.get('unreported_token_reserve', 0)}
        path = root / 'decisions.jsonl'
        stat = path.stat()
        detail = read_decisions(str(path), stat.st_size, stat.st_mtime_ns, model)
        if detail is None or detail['inputs'] > usage['input_tokens'] or detail['outputs'] > usage['output_tokens']:
            return empty
        missing_input = usage['input_tokens'] - detail['inputs']
        missing_output = usage['output_tokens'] - detail['outputs']
        # Aggregate residual usage has no request lengths. Include both context tiers.
        rates = PRICING['rates'][model]
        residual_low = (missing_input * rates[1] + missing_output * rates[2]) / 1e6
        multiplier = 5 if model == 'claude-haiku-5-5' else 2 if model.startswith('gpt-') else 1
        residual_high = (missing_input * rates[4] * multiplier + missing_output * rates[2] * multiplier) / 1e6
        complete = usage.get('accounting_complete', False)
        reserve = usage.get('unreported_token_reserve', 0) or 0
        # An interrupted call is capped by its reserve. Price it all as output at the top tier.
        reserve_high = 0 if complete else reserve * rates[2] * multiplier / 1e6
        note = ('Recorded usage with cache pricing range' if complete else
                'Interrupted call priced at its token reserve in the high estimate' if reserve else
                'Reported usage only. Unreported usage is not priced.')
        return {'low': detail['low'] + residual_low, 'high': detail['high'] + residual_high + reserve_high,
                'partial': not complete and not reserve, 'note': note,
                'recorded_tokens': total, 'cache_read_tokens': detail['cached'],
                'unreported_token_reserve': usage.get('unreported_token_reserve', 0),
                'missing_detail_tokens': missing_input + missing_output}
    except (OSError, ValueError, KeyError, TypeError):
        return empty


def sum_cost(rows):
    costs = [r['cost'] for r in rows if r.get('cost', {}).get('low') is not None]
    return {'low': sum(c['low'] for c in costs) if costs else None,
            'high': sum(c['high'] for c in costs) if costs else None,
            'partial': len(costs) != len(rows) or any(c['partial'] for c in costs),
            'priced': len(costs), 'planned': len(rows)}


def comparison(cells, models):
    """Compare equal category/group weights over the shared completed starts."""
    grouped = {m['id']: {} for m in models}
    for cell in cells:
        key = (cell['task_id'], cell.get('variant'))
        if cell['state'] == 'finished' and cell.get('value') is not None and cell.get('cost', {}).get('low') is not None:
            grouped[cell['model']][key] = cell
    shared = set.intersection(*(set(g) for g in grouped.values())) if grouped else set()
    output = []
    for model in models:
        rows = [grouped[model['id']][k] for k in sorted(shared)]
        groups = defaultdict(list)
        for row in rows:
            groups[(row['category'], row.get('score_group', row['task_id']))].append(row)
        categories = defaultdict(list)
        for (category, _), group in groups.items():
            categories[category].append({k: sum(r['cost'][k] for r in group) / len(group) for k in ('low', 'high')})
        costs = {k: sum(sum(g[k] for g in groups) / len(groups) for groups in categories.values()) / len(categories)
                 for k in ('low', 'high')} if categories else {'low': None, 'high': None}
        score = grouped_scores(rows)[1]
        output.append({'id': model['id'], 'label': model['label'], 'score': score, 'cost': costs,
                       'per_full_score': {k: v / score if v is not None and score else None for k, v in costs.items()},
                       'partial': any(r['cost']['partial'] for r in rows), 'starts': len(rows)})
    return {'starts': len(shared), 'models': output,
            'policy': 'Shared completed task starts, including failed tasks. Same category and group weights for score and mean cost. Full-score equivalent cost is mean cost divided by score, including fractional preparation credit. This is an exploratory comparison across the documented interface revisions.'}
