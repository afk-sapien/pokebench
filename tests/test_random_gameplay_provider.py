from pokeagent_bench.core import Limits
from pokeagent_bench.decision_contract import parse_response, wire_schema
from pokeagent_bench.random_gameplay_provider import RandomGameplayProvider

# The free smoke player. It calls no model, so these tests need no network and no ROM.


def decisions(seed, count=40):
    provider = RandomGameplayProvider('random', seed=seed, reasoning_effort='low')
    schema = provider.decision_schema(Limits())
    params = {'outputSchema': wire_schema(schema, provider.provider)}
    rows = []
    for _ in range(count):
        message, usage = provider._complete('turn/start', params, None)
        response, look_back, error = parse_response(message, schema, Limits())
        assert error is None and look_back is None and len(response['actions']) == 1
        assert usage == {'input_tokens': 0, 'output_tokens': 0, 'cached_input_tokens': 0}
        assert provider.context_tokens == 0
        rows.append(response['actions'][0])
    return provider, rows


def test_every_random_decision_passes_the_decision_contract_and_costs_nothing():
    provider, rows = decisions(7)
    assert provider.provider == 'random-gameplay' and provider.model == 'random'
    assert provider.config_identity['transport'] == 'none' and provider.config_identity['seed'] == 7
    assert len({str(row) for row in rows}) > 5


def test_the_same_seed_plays_the_same_game():
    assert decisions(7)[1] == decisions(7)[1]
    assert decisions(7)[1] != decisions(8)[1]
