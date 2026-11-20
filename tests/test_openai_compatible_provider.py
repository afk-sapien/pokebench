import json

import httpx
import pytest

from pokeagent_bench import quick_run
from pokeagent_bench.bounded_provider import BoundedGameplayProvider
from pokeagent_bench.codex_provider import CodexProvider
from pokeagent_bench.core import Limits
from pokeagent_bench.openai_compatible_provider import OpenAICompatibleProvider, probe
from pokeagent_bench.providers import ProviderError, SetupError

# No model is called here. A fake transport answers every request.
MOVE = {'actions': [{'command': 'move', 'argument': 'up', 'count': 2}]}
OBSERVATION = {'status': {'track': 'gameplay'}, 'frame': 7, 'controller_view': {'base64': 'AAAA', 'frame': 7}}


def reply(content=json.dumps(MOVE), usage={'prompt_tokens': 900, 'completion_tokens': 100,
                                           'prompt_tokens_details': {'cached_tokens': 300}}, status=200):
    body = {'model': 'llama3:8b-q4', 'choices': [{'message': {'role': 'assistant', 'content': content}}]}
    if usage is not None:
        body['usage'] = usage
    return httpx.Response(status, json=body)


def make(monkeypatch, *replies, key='secret-key', base='http://localhost:11434/v1/'):
    """A provider whose endpoint returns the given replies in order and records each request."""
    monkeypatch.setenv('POKEBENCH_BASE_URL', base)
    if key:
        monkeypatch.setenv('POKEBENCH_API_KEY', key)
    else:
        monkeypatch.delenv('POKEBENCH_API_KEY', raising=False)
    requests, pending = [], list(replies)

    def handler(request):
        requests.append(request)
        return pending.pop(0)

    value = OpenAICompatibleProvider('llama3:8b', transport=httpx.MockTransport(handler))
    # The packet builder needs a real game observation, so stand in a fixed packet.
    monkeypatch.setattr(value, 'prepare_packet', lambda observation, notes, recent: (
        {}, {'segment': value.segment_index + (value.packet_baseline is None), 'sequence': value.packet_sequence + 1},
        'baseline', 'Current observation', value.packet_baseline is None))
    return value, requests


def decide(value):
    return value.decide(OBSERVATION, '', [], Limits(), 60)


def test_two_turns_keep_one_conversation_and_report_usage(monkeypatch):
    value, requests = make(monkeypatch, reply(), reply('```json\n' + json.dumps(MOVE) + '\n```'))
    decision, usage, record = decide(value)
    assert decision['actions'] == MOVE['actions']
    assert usage == {'input_tokens': 900, 'output_tokens': 100, 'cached_input_tokens': 300}
    assert value.context_tokens == 1000
    assert record['resolved_model'] == 'llama3:8b-q4' and record['segment_start'] is True
    first = json.loads(requests[0].content)
    assert str(requests[0].url) == 'http://localhost:11434/v1/chat/completions'
    assert requests[0].headers['authorization'] == 'Bearer secret-key'
    assert first['model'] == 'llama3:8b'
    assert [message['role'] for message in first['messages']] == ['system', 'user']
    assert first['messages'][0]['content'] == value.prompt
    assert first['messages'][1]['content'][0] == {'type': 'text', 'text': 'Current observation'}
    assert first['messages'][1]['content'][-1] == {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,AAAA'}}
    assert first['response_format']['json_schema']['schema'] == value.decision_schema(Limits())
    # A fenced answer is accepted, and the second call resends the whole segment.
    decision, _, record = decide(value)
    assert decision['actions'] == MOVE['actions'] and record['segment_start'] is False
    assert [message['role'] for message in json.loads(requests[1].content)['messages']] == ['system', 'user', 'assistant', 'user']


def test_run_identity_matches_the_shared_protocol_and_holds_no_secret(monkeypatch):
    value, _ = make(monkeypatch, base='http://user:hidden@localhost:11434/v1')
    monkeypatch.setattr(CodexProvider, '_initialize_cli', lambda self: None)
    codex = BoundedGameplayProvider('gpt-6-astra')
    assert value.prompt == codex.prompt
    assert value.context_turns == codex.context_turns and value.compact_at == codex.compact_at
    assert value.config_identity['endpoint'] == 'http://localhost:11434/v1'
    assert 'secret-key' not in json.dumps(value.config_identity) and 'hidden' not in json.dumps(value.config_identity)


def test_a_restart_begins_a_new_segment_with_a_full_snapshot(monkeypatch):
    value, requests = make(monkeypatch, reply(), reply(), key=None)
    decide(value)
    value.close()
    _, _, record = decide(value)
    assert record['segment_start'] is True and record['segment'] == 2
    assert [message['role'] for message in json.loads(requests[1].content)['messages']] == ['system', 'user']
    assert 'authorization' not in requests[1].headers


def test_unusable_answers_are_metered_and_rejected_without_an_action(monkeypatch):
    value, _ = make(monkeypatch, reply('I would walk north.'), reply(None))
    for _ in range(2):
        decision, usage, record = decide(value)
        assert decision['actions'] == [] and 'response_validation_error' in record
        assert usage['input_tokens'] == 900


@pytest.mark.parametrize('response, message', [
    (reply(status=500), 'HTTP 500'),
    (reply(usage=None), 'no token usage'),
    (reply(usage={'prompt_tokens': 0, 'completion_tokens': 0}), 'no token usage'),
    (httpx.Response(200, text='not json'), 'Invalid bounded provider response'),
])
def test_endpoint_failures_stop_the_run(monkeypatch, response, message):
    value, _ = make(monkeypatch, response)
    with pytest.raises(ProviderError, match=message):
        decide(value)


def test_a_refused_connection_sent_nothing_so_the_run_asks_again(monkeypatch):
    # The runner retries a no_reply error and then pauses the run, so the same command resumes it.
    for failure in (httpx.ConnectError('refused'), httpx.ConnectTimeout('slow')):
        def refuse(request, failure=failure):
            raise failure
        monkeypatch.setenv('POKEBENCH_BASE_URL', 'http://localhost:11434/v1')
        value = OpenAICompatibleProvider('llama3:8b', transport=httpx.MockTransport(refuse))
        monkeypatch.setattr(value, 'prepare_packet', lambda observation, notes, recent: (
            {}, {'segment': 1, 'sequence': 1}, 'baseline', 'Current observation', True))
        with pytest.raises(ProviderError, match='Could not connect') as raised:
            decide(value)
        assert raised.value.details == {'kind': 'provider_error', 'no_reply': True}
    # A request that was sent and then failed may have been billed, so it is not a no_reply error.
    def drop(request):
        raise httpx.ReadTimeout('no answer')
    value = OpenAICompatibleProvider('llama3:8b', transport=httpx.MockTransport(drop))
    monkeypatch.setattr(value, 'prepare_packet', lambda observation, notes, recent: (
        {}, {'segment': 1, 'sequence': 1}, 'baseline', 'Current observation', True))
    with pytest.raises(ProviderError, match='Usage may be unreported') as raised:
        decide(value)
    assert raised.value.details.get('no_reply') is not True


def answer(status=200, body=None, seen=None):
    def handler(request):
        if seen is not None:
            seen.append(request)
        return httpx.Response(status, json=body if body is not None else {'data': []})
    return httpx.MockTransport(handler)


def test_the_probe_reads_the_model_list_and_names_the_endpoint(monkeypatch):
    monkeypatch.setenv('POKEBENCH_BASE_URL', 'http://localhost:11434/v1/')
    monkeypatch.setenv('POKEBENCH_API_KEY', 'secret-key')
    seen = []
    listed = {'data': [{'id': 'llama3:8b'}, {'id': 'qwen3:32b'}]}
    assert probe('llama3:8b', transport=answer(body=listed, seen=seen)) == [
        'Model endpoint http://localhost:11434/v1 answered.']
    assert seen[0].method == 'GET' and str(seen[0].url) == 'http://localhost:11434/v1/models'
    assert seen[0].headers['authorization'] == 'Bearer secret-key'
    # The plan line never shows credentials from the URL.
    monkeypatch.setenv('POKEBENCH_BASE_URL', 'http://user:hidden@localhost:11434/v1/')
    assert probe('llama3:8b', transport=answer(body=listed)) == ['Model endpoint http://localhost:11434/v1 answered.']
    assert probe('llama3:70b', transport=answer(body=listed))[1] == (
        'It does not list llama3:70b. It lists llama3:8b, qwen3:32b.')
    many = {'data': [{'id': f'model-{index}'} for index in range(7)]}
    assert probe('x', transport=answer(body=many))[1].endswith('model-4 and more.')
    # A server without a model list still answered, so the plan only names it.
    for transport in (answer(status=404), answer(body={'object': 'list'}), answer(body=[1, 2])):
        assert probe('llama3:8b', transport=transport) == ['Model endpoint http://localhost:11434/v1 answered.']


def test_the_probe_stops_on_a_missing_url_a_refused_key_or_no_server(monkeypatch):
    monkeypatch.delenv('POKEBENCH_BASE_URL', raising=False)
    with pytest.raises(SetupError, match='Set POKEBENCH_BASE_URL'):
        probe('llama3:8b', transport=answer())
    monkeypatch.setenv('POKEBENCH_BASE_URL', 'http://localhost:11434/v1')
    for status in (401, 403):
        with pytest.raises(SetupError, match=f'refused the request with HTTP {status}. Set POKEBENCH_API_KEY'):
            probe('llama3:8b', transport=answer(status=status))

    def refuse(request):
        raise httpx.ConnectError('refused')
    with pytest.raises(SetupError, match=r'http://localhost:11434/v1 did not answer \(ConnectError\). Start the server'):
        probe('llama3:8b', transport=httpx.MockTransport(refuse))


def test_missing_endpoint_and_suite_model_names(monkeypatch):
    monkeypatch.delenv('POKEBENCH_BASE_URL', raising=False)
    with pytest.raises(SetupError, match='POKEBENCH_BASE_URL'):
        OpenAICompatibleProvider('llama3:8b')
    assert quick_run.resolve_model('openai-compatible', 'llama3:8b') == ('openai-compatible', 'llama3:8b')
    assert quick_run.resolve_model(None, 'openai-compatible:llama3:8b') == ('openai-compatible', 'llama3:8b')
