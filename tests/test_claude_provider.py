from collections import deque
from types import SimpleNamespace
import json
import time

import pytest

from pokeagent_bench.bounded_provider import BoundedGameplayProvider
from pokeagent_bench.claude_provider import ClaudeCodeProvider, subscription_environment, usage_delta
from pokeagent_bench.codex_provider import CodexProvider
from pokeagent_bench.core import Limits
from pokeagent_bench.providers import ProviderError

MODEL = 'claude-sonnet-5-5'


def test_accounting_counts_cache_once_and_subtracts_previous_turns():
    first = dict(inputTokens=100, outputTokens=20, cacheReadInputTokens=200, cacheCreationInputTokens=50)
    usage, prior = usage_delta({MODEL: first}, MODEL, {})
    assert usage['input_tokens'] == 350
    assert usage['output_tokens'] == 20
    second = {key: value * 2 for key, value in first.items()}
    assert usage_delta({MODEL: second}, MODEL, prior)[0] == usage
    with pytest.raises(ProviderError, match='decreased'):
        usage_delta({MODEL: first}, MODEL, second)
    with pytest.raises(ProviderError, match='Unexpected model'):
        usage_delta({MODEL: first, 'other-model': first}, MODEL, {})
    with pytest.raises(ProviderError, match='Incomplete'):
        usage_delta({MODEL: {'inputTokens': True}}, MODEL, {})


def test_api_and_provider_environment_overrides_are_removed(monkeypatch):
    for key in ('ANTHROPIC_API_KEY', 'ANTHROPIC_BASE_URL', 'CLAUDE_CODE_USE_BEDROCK', 'CLAUDE_CODE_OAUTH_TOKEN', 'CLAUDE_CONFIG_DIR'):
        monkeypatch.setenv(key, 'must-not-reach-cli')
    env = subscription_environment()
    assert 'must-not-reach-cli' not in env.values()
    assert env['CLAUDE_CODE_DISABLE_AUTO_COMPACT'] == '1'


def test_prompt_schema_and_bounded_policy_match_codex(monkeypatch):
    monkeypatch.setattr(CodexProvider, '_initialize_cli', lambda self: None)
    monkeypatch.setattr(ClaudeCodeProvider, '_initialize_cli', lambda self: None)
    codex = BoundedGameplayProvider('gpt-6-astra', reasoning_effort='medium')
    claude = ClaudeCodeProvider(MODEL, reasoning_effort='medium')
    assert claude.prompt == codex.prompt
    assert claude.decision_schema(Limits()) == codex.decision_schema(Limits())
    assert claude.context_turns == codex.context_turns == 8
    assert claude.compact_at == codex.compact_at == 12000
    assert claude.memory_protocol == codex.memory_protocol
    with pytest.raises(ValueError, match='exact'):
        ClaudeCodeProvider('sonnet')
    with pytest.raises(ValueError, match='credits'):
        ClaudeCodeProvider('claude-fable-5-1')


def provider(events):
    value = object.__new__(ClaudeCodeProvider)
    pending = deque(events)
    value.server = SimpleNamespace(send=lambda event: None, event=lambda deadline: pending.popleft())
    value.model = MODEL
    value.thread_id = None
    value.total_usage = {}
    value.response_contract = "compact"
    value.schema = value.decision_schema(Limits())
    return value


def complete(value):
    return value._complete('turn/start', {'input': [{'type': 'text', 'text': 'Current observation'}]}, time.monotonic() + 10)


@pytest.mark.parametrize('event', [
    {'type': 'system', 'subtype': 'init', 'model': MODEL, 'tools': ['Read'], 'session_id': 'x'},
    {'type': 'system', 'subtype': 'init', 'model': 'other', 'tools': [], 'session_id': 'x'},
    {'type': 'system', 'subtype': 'compact_boundary'},
    {'type': 'assistant', 'message': {'model': MODEL, 'content': [{'type': 'tool_use', 'name': 'Bash'}]}},
    {'type': 'assistant', 'message': {'model': 'other', 'content': []}},
    {'type': 'result', 'subtype': 'error_max_budget_usd', 'is_error': True},
])
def test_transport_fails_closed_on_tools_fallback_or_compaction(event):
    with pytest.raises(ProviderError):
        complete(provider([event]))


def test_structured_decision_returns_usage_and_session_identity():
    value = provider([
        {'type': 'system', 'subtype': 'init', 'model': MODEL, 'tools': ['StructuredOutput'], 'mcp_servers': [], 'session_id': 'exact-session'},
        {'type': 'result', 'subtype': 'success', 'is_error': False, 'structured_output': {'actions': []},
         'usage': {'input_tokens': 2, 'cache_read_input_tokens': 40, 'cache_creation_input_tokens': 8, 'output_tokens': 10},
         'modelUsage': {MODEL: dict(inputTokens=2, outputTokens=10, cacheReadInputTokens=40, cacheCreationInputTokens=8)}}
    ])
    message, usage = complete(value)
    assert json.loads(message) == {'actions': [], 'notes': None, 'goal_plan': None, 'look_back': None}
    assert usage['input_tokens'] == 50
    assert value.context_tokens == 60
    assert value.thread_id == 'exact-session'


def test_response_headroom_is_recorded_and_reserved_before_a_decision(monkeypatch):
    monkeypatch.setattr(ClaudeCodeProvider, '_initialize_cli', lambda self: None)
    value = ClaudeCodeProvider(MODEL, reasoning_effort='medium')
    monkeypatch.setattr(value, 'prepare_packet', lambda *args: ({}, {}, {}, 'observation', False))
    value.context_tokens = 10000
    value.look_back = None
    assert int(subscription_environment()['CLAUDE_CODE_MAX_OUTPUT_TOKENS']) == value.max_output_tokens == 8192
    assert value.harness == 'claude-code-bounded-gameplay-v2'
    assert value.estimate_next_tokens({}, None, [], Limits()) == 10000 + len('observation') + 2048 + 8192


def response(value=None, *, subtype='success', tokens=100):
    return {'type': 'result', 'subtype': subtype, 'is_error': subtype != 'success',
            'structured_output': value,
            'modelUsage': {MODEL: dict(inputTokens=tokens, outputTokens=tokens,
                                      cacheReadInputTokens=0, cacheCreationInputTokens=0)}}


def test_optional_wire_fields_do_not_relax_actions():
    from pokeagent_bench.claude_interface import wire_schema, normalize
    schema = provider([]).schema
    assert wire_schema(schema)['required'] == ['actions']
    assert set(schema['required']) == {'actions', 'notes', 'goal_plan', 'look_back'}
    valid = {'actions': [{'command': 'use_move', 'argument': '1', 'count': 1}]}
    assert normalize(valid, schema)['goal_plan'] is None
    for malformed in ({}, {'actions': [{'command': 'use_move'}]},
                      {'actions': [{'command': 'Bash', 'argument': '', 'count': 1}]},
                      {**valid, 'look_back': True}, {**valid, 'goal_plan': 'null'}):
        with pytest.raises(ValueError):
            normalize(malformed, schema)


def test_game_tool_is_never_dispatched_and_later_valid_structured_output_is_accepted():
    value = provider([
        {'type': 'assistant', 'message': {'model': MODEL, 'content': [
            {'type': 'tool_use', 'name': 'use_move', 'input': {'argument': '4', 'count': 1}}]}},
        response({'actions': [{'command': 'use_move', 'argument': '2', 'count': 1}]})])
    message, usage = complete(value)
    assert json.loads(message)['actions'][0]['argument'] == '2'
    assert usage['output_tokens'] == 100
    assert value.interface_record['unavailable_game_tools'] == ['use_move']


def test_failed_structured_result_is_metered_before_next_decision_correction():
    value = provider([response(subtype='error_max_structured_output_retries'),
                      response({'actions': [{'command': 'use_move', 'argument': '1', 'count': 1}]}, tokens=250)])
    sent = []
    value.server.send = sent.append
    message, usage = complete(value)
    assert json.loads(message)['actions'] == []
    assert 'interface_error' in json.loads(message)
    assert usage['input_tokens'] + usage['output_tokens'] == 200
    message, usage = complete(value)
    assert usage['input_tokens'] + usage['output_tokens'] == 300
    assert 'No action was executed' in sent[-1]['message']['content'][-1]['text']
    assert value.interface_feedback is None
    assert 'interface_error' not in json.loads(message)


def test_malformed_action_is_not_repaired_into_a_game_action():
    value = provider([response({'actions': [{'command': 'use_move', 'count': 1}]})])
    message, usage = complete(value)
    assert json.loads(message)['actions'] == []
    assert usage['output_tokens'] == 100
    assert value.interface_record['correction_needed']


def test_recoverable_error_without_accounting_still_fails_closed():
    value = provider([{'type': 'result', 'subtype': 'error_max_structured_output_retries', 'is_error': True}])
    with pytest.raises(ProviderError, match='Unexpected model'):
        complete(value)
