import json

import pytest

from pokeagent_bench.showcase_costs import comparison, price_usage, run_cost, sum_cost


def test_prices_normalized_input_without_double_counting_cache():
    usage = {'input_tokens': 100000, 'cached_input_tokens': 60000,
             'cache_creation_input_tokens': 30000, 'output_tokens': 1000}
    cost = price_usage('claude-opus-5-5', usage)
    assert cost['low'] == pytest.approx((10000 * 4 + 60000 * .2 + 30000 * 5 + 1000 * 20) / 1e6)
    assert cost['high'] == pytest.approx((10000 * 4 + 60000 * .2 + 30000 * 8 + 1000 * 20) / 1e6)


def test_unknown_cache_write_is_range_and_unknown_model_is_not_free():
    usage = {'input_tokens': 100000, 'cached_input_tokens': 60000, 'output_tokens': 1000}
    cost = price_usage('gpt-6-astra', usage)
    assert cost == {'low': .51, 'high': .61}
    assert price_usage('unknown', usage) is None
    assert price_usage('gpt-6-astra', dict(usage, cached_input_tokens=100001)) is None
    assert sum_cost([{'cost': {'low': None}}])['low'] is None


def test_long_context_is_priced_per_request():
    usage = {'input_tokens': 100001, 'cached_input_tokens': 0,
             'cache_creation_input_tokens': 0, 'output_tokens': 1000}
    assert price_usage('claude-haiku-5-5', usage)['low'] == pytest.approx(.0525005)


def test_missing_terminal_usage_included_and_reserve_bounds_high(tmp_path):
    detail = {'input_tokens': 100, 'cached_input_tokens': 50, 'output_tokens': 10}
    (tmp_path / 'decisions.jsonl').write_text(json.dumps({'usage': detail}) + '\n')
    usage = {'input_tokens': 150, 'output_tokens': 30, 'accounting_complete': False,
             'unreported_token_reserve': 64000}
    (tmp_path / 'result.json').write_text(json.dumps({'usage': usage}))
    cost = run_cost(tmp_path, 'gpt-6-astra', 180)
    assert not cost['partial']
    assert cost['recorded_tokens'] == 180
    assert cost['missing_detail_tokens'] == 70
    assert cost['unreported_token_reserve'] == 64000
    assert cost['low'] > price_usage('gpt-6-astra', detail)['low']
    assert cost['high'] == pytest.approx(cost['low'] + 64000 * 50 * 2 / 1e6, abs=.01)
    assert run_cost(tmp_path, 'gpt-6-astra', 181)['low'] is None
    usage['unreported_token_reserve'] = 0
    (tmp_path / 'result.json').write_text(json.dumps({'usage': usage}))
    assert run_cost(tmp_path, 'gpt-6-astra', 180)['partial']


def test_shared_value_includes_failures_and_fractional_credit():
    def cell(model, task, value, cost, state='finished'):
        return {'model': model, 'task_id': task, 'score_group': task, 'variant': 'default',
                'category': 'battle', 'state': state, 'value': value,
                'cost': {'low': cost, 'high': cost * 2, 'partial': False}}
    cells = [cell('a', 'win', 1, 2), cell('a', 'loss', 0, 8),
             cell('b', 'win', .5, 1), cell('b', 'loss', 0, 1),
             cell('a', 'pending', 1, 100), cell('b', 'pending', None, 0, 'pending')]
    result = comparison(cells, [{'id': m, 'label': m} for m in ('a', 'b')])
    assert result['starts'] == 2
    a, b = result['models']
    assert a['score'] == .5
    assert a['cost']['low'] == 5
    assert a['per_full_score']['low'] == 10
    assert b['score'] == .25
    assert b['per_full_score']['low'] == 4
