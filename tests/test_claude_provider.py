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
    assert json.loads(message) == {'actions': []}
    assert usage['input_tokens'] == 50
    assert value.context_tokens == 60
    assert value.thread_id == 'exact-session'
