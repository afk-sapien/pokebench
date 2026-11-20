"""Any OpenAI compatible chat endpoint as a transport for the shared bounded gameplay protocol.

Set POKEBENCH_BASE_URL, for example http://localhost:11434/v1, and POKEBENCH_API_KEY
if the server needs a key. The key is never written to a run.
"""
import os
import time
from urllib.parse import urlsplit

import httpx

from .bounded_provider import BoundedGameplayProvider
from .providers import ProviderError, SetupError

PROBE_SECONDS = 10


def endpoint_settings():
    """The base URL, the address a run records and the key, read from POKEBENCH_BASE_URL and POKEBENCH_API_KEY."""
    base = os.environ.get('POKEBENCH_BASE_URL', '').rstrip('/')
    parts = urlsplit(base)
    if parts.scheme not in ('http', 'https') or not parts.hostname:
        raise SetupError('Set POKEBENCH_BASE_URL to an OpenAI compatible endpoint, '
                         'for example http://localhost:11434/v1')
    # Recorded in the run, so it leaves out any credentials in the URL.
    endpoint = f'{parts.scheme}://{parts.hostname}' + (f':{parts.port}' if parts.port else '') + parts.path
    return base, endpoint, os.environ.get('POKEBENCH_API_KEY')


def probe(model, *, transport=None):
    """Check that the endpoint answers before a suite run asks to start, and return the plan lines.

    It reads the model list only, so no model runs and no tokens are spent.
    """
    base, endpoint, key = endpoint_settings()
    try:
        with httpx.Client(transport=transport, follow_redirects=False) as client:
            response = client.get(base + '/models', timeout=PROBE_SECONDS,
                                  headers={'Authorization': 'Bearer ' + key} if key else {})
    except httpx.HTTPError as error:
        raise SetupError(f'The model endpoint {endpoint} did not answer ({type(error).__name__}). '
                         'Start the server or fix POKEBENCH_BASE_URL') from None
    if response.status_code in (401, 403):
        raise SetupError(f'The model endpoint {endpoint} refused the request with HTTP {response.status_code}. '
                         'Set POKEBENCH_API_KEY to a key it accepts')
    lines = [f'Model endpoint {endpoint} answered.']
    try:
        rows = response.json()['data'] if response.status_code == 200 else []
        listed = sorted({row['id'] for row in rows if isinstance(row, dict) and isinstance(row.get('id'), str)})
    except (ValueError, KeyError, TypeError):
        listed = []
    # A server that lists its models but not this one usually means a typo in --model.
    if listed and model not in listed:
        lines.append(f'It does not list {model}. It lists ' + ', '.join(listed[:5])
                     + (' and more.' if len(listed) > 5 else '.'))
    return lines


class OpenAICompatibleProvider(BoundedGameplayProvider):
    provider = 'openai-compatible'
    harness = 'openai-compatible-chat-gameplay-bounded-v1'

    def __init__(self, model, *, transport=None, **kwargs):
        self.transport = transport
        self.resolved_model = None
        super().__init__(model, **kwargs)
        self.config_identity.update(transport='chat-completions-v1', endpoint=self.endpoint, tools='none',
            effort_control_supported=False, effective_effort=None,
            context_persistence='segment-messages-resent-each-call',
            usage_accounting='reported-prompt-plus-completion-tokens-per-call-v1')

    def _initialize_cli(self):
        base, self.endpoint, self.key = endpoint_settings()
        self.url = base + '/chat/completions'
        self.cli_version = None

    def decide(self, observation, notes, recent, limits, timeout):
        if self.server is None:
            # The conversation lives in this process. After a restart, begin a new segment with a full snapshot.
            self.packet_baseline = None
        decision, usage, record = super().decide(observation, notes, recent, limits, timeout)
        record.update(resolved_model=self.resolved_model, transport='chat-completions-v1')
        return decision, usage, record

    def _start(self, deadline):
        self.messages = [{'role': 'system', 'content': self.prompt}]
        self.server = httpx.Client(transport=self.transport, follow_redirects=False)

    def _complete(self, method, params, deadline):
        content = [{'type': 'text', 'text': item['text']} if item['type'] == 'text' else
                   {'type': 'image_url', 'image_url': {'url': item['url']}} for item in params['input']]
        self.messages.append({'role': 'user', 'content': content})
        body = {'model': self.model, 'messages': self.messages, 'response_format': {
            'type': 'json_schema', 'json_schema': {'name': 'decision', 'schema': params['outputSchema']}}}
        try:
            response = self.server.post(self.url, json=body, timeout=max(1, deadline - time.monotonic()),
                                        headers={'Authorization': 'Bearer ' + self.key} if self.key else {})
        except (httpx.ConnectError, httpx.ConnectTimeout) as error:
            # The connection never opened, so nothing was sent or spent. The run asks again, then pauses at this
            # decision, and the same command resumes it.
            raise ProviderError(f'Could not connect to the model endpoint ({type(error).__name__}). Nothing was sent',
                                details={'kind': 'provider_error', 'no_reply': True}) from None
        except httpx.HTTPError as error:
            raise ProviderError(f'Model endpoint failed: {type(error).__name__}. Usage may be unreported') from None
        if response.status_code != 200:
            raise ProviderError(f'Model endpoint returned HTTP {response.status_code}. Usage may be unreported',
                                details={'body': response.text[:500]})
        data = response.json()
        usage = data.get('usage') or {}
        sent, made = usage.get('prompt_tokens'), usage.get('completion_tokens')
        if type(sent) is not int or type(made) is not int or sent < 0 or made < 0 or sent + made == 0:
            raise ProviderError('The endpoint reported no token usage, so this run cannot be scored')
        cached = (usage.get('prompt_tokens_details') or {}).get('cached_tokens')
        text = data['choices'][0]['message'].get('content')
        text = text if isinstance(text, str) else ''
        self.messages.append({'role': 'assistant', 'content': text})
        self.resolved_model = data.get('model')
        self.context_tokens = sent + made
        # Some models wrap the JSON object in a code fence or a sentence. Nothing inside it is changed.
        start, end = text.find('{'), text.rfind('}')
        return text[start:end + 1] if start >= 0 else text, {
            'input_tokens': sent, 'output_tokens': made, 'cached_input_tokens': cached if type(cached) is int else 0}
