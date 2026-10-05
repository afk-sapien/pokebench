import json

import pytest

from pokeagent_bench.costs import efficiency, enrich, estimate


def test_cache_discount_and_model_rates():
    usage = dict(input_tokens=1_000_000, cached_input_tokens=800_000, output_tokens=10_000)
    assert estimate('gpt-6-astra', usage) == 82.5
    assert estimate('gpt-6-luna', usage) == 0.825
    assert estimate('missing', usage) is None
    assert estimate('gpt-6-astra', {**usage, 'cached_input_tokens': 1_000_001}) is None
    assert estimate('gpt-6-astra', {'input_tokens': 1}) is None


def test_usage_reconciliation_and_interrupted_call(tmp_path):
    usage = dict(input_tokens=1000, cached_input_tokens=800, output_tokens=10)
    (tmp_path/'decisions.jsonl').write_text(json.dumps({'usage': usage})+'\n')
    result = {'usage': {**usage, 'calls': 1, 'accounting_complete': True}}
    (tmp_path/'result.json').write_text(json.dumps(result))
    attempt = dict(model='gpt-6-astra', status='finished')
    enrich(attempt, tmp_path)
    assert attempt['estimated_credits'] == pytest.approx(0.0825)
    assert attempt['cost_complete']
    attempt['prior_interruptions'] = [{'accounting_complete': False}]
    enrich(attempt, tmp_path)
    assert not attempt['cost_complete']
    assert attempt['estimated_credits'] == pytest.approx(0.0825)
    attempt.pop('prior_interruptions')
    result['usage']['input_tokens'] += 1
    (tmp_path/'result.json').write_text(json.dumps(result))
    enrich(attempt, tmp_path)
    assert not attempt['cost_complete']


def test_missing_cache_usage_is_unknown(tmp_path):
    (tmp_path/'decisions.jsonl').write_text(json.dumps({'usage': {'input_tokens': 10}})+'\n')
    (tmp_path/'result.json').write_text(json.dumps({'usage': {}}))
    attempt = dict(model='gpt-6-astra', status='finished')
    enrich(attempt, tmp_path)
    assert attempt['estimated_credits'] is None
    assert not attempt['cost_complete']


def test_cost_per_success_includes_failures_and_equal_task_weights():
    rows = []
    for model in ['a', 'b']:
        for task, wins, cost in [('one', [True], 10), ('two', [False, False], 20), ('unknown', [True], 500)]:
            for won in wins:
                rows.append(dict(model=model, task=task, completed=won if model=='a' else False,
                                 estimated_credits=cost, cost_complete=not (task=='unknown' and model=='b')))
    result = efficiency(rows, ['a', 'b'], ['one', 'two', 'unknown'])
    assert result['task_ids'] == ['one', 'two']
    a, b = result['models']
    assert a['credits_per_attempt'] == 15
    assert a['credits_per_success'] == 30
    assert a['cost_success_rate'] == 50
    assert b['credits_per_success'] is None
    assert efficiency([], ['a'], [])['models'][0]['credits_per_attempt'] is None
