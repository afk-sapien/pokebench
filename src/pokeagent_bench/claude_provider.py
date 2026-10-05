"""Claude Code subscription transport for the shared bounded gameplay protocol."""
from __future__ import annotations

import json
import os
import queue
import re
import subprocess
import tempfile
import threading
import time

from .bounded_provider import BoundedGameplayProvider
from .providers import ProviderError


def subscription_environment():
    """Keep the official login, excluding alternate providers and credential overrides."""
    excluded = ('ANTHROPIC_', 'CLAUDE_CODE_', 'CLAUDE_CONFIG_DIR', 'CLAUDE_AGENT_', 'CLAUDE_SESSION_', 'CLAUDECODE')
    env = {key: value for key, value in os.environ.items() if not key.startswith(excluded)}
    env.update(CLAUDE_CODE_DISABLE_AUTO_COMPACT='1', CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC='1',
               CLAUDE_CODE_MAX_OUTPUT_TOKENS='4096')
    return env


def subscription_status(executable, env):
    result = subprocess.run([executable, 'auth', 'status'], capture_output=True, text=True,
                            timeout=15, env=env, cwd='/tmp', check=True)
    status = json.loads(result.stdout)
    if not status.get('loggedIn') or status.get('authMethod') != 'claude.ai' or status.get('apiProvider') != 'firstParty':
        raise ValueError('Sign into Claude Code with a Claude subscription before this run')
    return {key: status.get(key) for key in ('loggedIn', 'authMethod', 'apiProvider', 'subscriptionType')}


def usage_delta(models, model, previous):
    """modelUsage is cumulative. Cache reads and writes are additional input tokens."""
    if set(models) != {model}:
        raise ProviderError('Unexpected model usage. Fallback or outside model call invalidates this trial')
    raw = models[model]
    names = ('inputTokens', 'outputTokens', 'cacheReadInputTokens', 'cacheCreationInputTokens')
    if any(type(raw.get(key)) is not int or raw[key] < 0 for key in names):
        raise ProviderError('Incomplete Claude token accounting')
    total = {key: raw[key] for key in names}
    delta = {key: total[key] - previous.get(key, 0) for key in names}
    if any(value < 0 for value in delta.values()):
        raise ProviderError('Claude cumulative token usage decreased')
    return {'input_tokens': delta['inputTokens'] + delta['cacheReadInputTokens'] + delta['cacheCreationInputTokens'],
            'output_tokens': delta['outputTokens'], 'cached_input_tokens': delta['cacheReadInputTokens'],
            'cache_creation_input_tokens': delta['cacheCreationInputTokens']}, total


class ClaudeStream:
    def __init__(self, command, directory, env):
        self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, cwd=directory, env=env, bufsize=1)
        self.events = queue.Queue()
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        try:
            for line in self.process.stdout:
                self.events.put(json.loads(line))
        except (ValueError, OSError):
            self.events.put({'type': 'transport_error'})
        finally:
            self.events.put({'type': 'transport_closed'})

    def send(self, event):
        self.process.stdin.write(json.dumps(event) + '\n')
        self.process.stdin.flush()

    def event(self, deadline):
        try:
            return self.events.get(timeout=max(0.001, deadline - time.monotonic()))
        except queue.Empty:
            raise ProviderError('Claude decision timed out. Usage may be unreported') from None

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        for pipe in (self.process.stdin, self.process.stdout):
            pipe.close()


class ClaudeCodeProvider(BoundedGameplayProvider):
    provider = 'claude-code'
    harness = 'claude-code-bounded-gameplay-v1'
    max_output_tokens = 4096

    def __init__(self, model, *, executable='claude', **kwargs):
        if not re.fullmatch(r'claude-[a-z]+-[0-9][a-z0-9-]*', model):
            raise ValueError('Use an exact Claude model ID, not an alias')
        if 'fable' in model:
            raise ValueError('Fable may require usage credits and is excluded from the subscription adapter')
        super().__init__(model, executable=executable, **kwargs)
        self.config_identity.update(transport='claude-code-stream-json-v1',
            tools='none', subscription_only=True, automatic_compaction=False,
            effort_control_supported='haiku' not in model,
            effective_effort=None if 'haiku' in model else self.reasoning_effort,
            context_persistence='retained-segments-cli-session-resume',
            usage_accounting='cumulative-model-usage-delta-including-cache-v1')

    def _initialize_cli(self):
        self.env = subscription_environment()
        try:
            self.auth = subscription_status(self.executable, self.env)
            result = subprocess.run([self.executable, '--version'], capture_output=True, text=True,
                timeout=15, env=self.env, check=True)
            self.cli_version = result.stdout.strip()
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
            raise ValueError('Claude Code subscription CLI is unavailable') from None

    def decide(self, observation, notes, recent, limits, timeout):
        self.schema = self.decision_schema(limits)
        decision, usage, record = super().decide(observation, notes, recent, limits, timeout)
        record.update(resolved_model=self.model, subscription=self.auth['subscriptionType'],
                      transport='claude-code-stream-json-v1')
        return decision, usage, record

    def _start(self, deadline):
        self.temporary = tempfile.TemporaryDirectory(prefix='pokebench-claude-')
        command = [self.executable, '-p', '--safe-mode', '--restricted', '--tools', '',
            '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}', '--setting-sources', '',
            '--disable-slash-commands', '--no-chrome', '--permission-mode', 'dontAsk',
            '--input-format', 'stream-json', '--output-format', 'stream-json',
            '--verbose', '--model', self.model, '--effort', self.reasoning_effort,
            '--system-prompt', self.prompt, '--json-schema', json.dumps(self.schema),
            '--settings', '{"disableAllHooks":true,"autoMemoryEnabled":false,"fallbackModel":[]}']
        if self.thread_id is not None:
            command.extend(['--resume', self.thread_id])
        else:
            self.total_usage = {}
        self.server = ClaudeStream(command, self.temporary.name, self.env)

    def _complete(self, method, params, deadline):
        content = []
        for item in params['input']:
            if item['type'] == 'text':
                content.append({'type': 'text', 'text': item['text']})
            else:
                content.append({'type': 'image', 'source': {'type': 'base64',
                    'media_type': 'image/png', 'data': item['url'].split(',', 1)[1]}})
        self.server.send({'type': 'user', 'message': {'role': 'user', 'content': content}})
        while True:
            event = self.server.event(deadline)
            kind = event.get('type')
            if kind in ('transport_error', 'transport_closed'):
                raise ProviderError('Claude transport ended. Usage may be unreported')
            if kind == 'system' and event.get('subtype') == 'init':
                if event.get('model') != self.model or event.get('mcp_servers') or set(event.get('tools', [])) != {'StructuredOutput'}:
                    raise ProviderError('Claude model or tool isolation mismatch')
                if self.thread_id is not None and event['session_id'] != self.thread_id:
                    raise ProviderError('Claude resumed a different session')
                self.thread_id = event['session_id']
            if kind == 'system' and event.get('subtype') == 'compact_boundary':
                raise ProviderError('Unexpected automatic compaction invalidates this trial')
            if kind == 'assistant':
                message = event['message']
                if message.get('model') != self.model:
                    raise ProviderError('Claude resolved a different model')
                if any(block.get('type') == 'tool_use' and block.get('name') != 'StructuredOutput'
                       for block in message.get('content', [])):
                    raise ProviderError('Claude attempted an outside tool')
            if kind == 'result':
                if event.get('is_error') or event.get('subtype') != 'success':
                    raise ProviderError('Claude did not complete a decision. Usage may be unreported')
                usage, self.total_usage = usage_delta(event.get('modelUsage', {}), self.model, self.total_usage)
                last = event.get('usage', {})
                self.context_tokens = sum(last.get(key, 0) for key in
                    ('input_tokens', 'output_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens'))
                if not isinstance(event.get('structured_output'), dict):
                    raise ProviderError('Claude returned no structured decision. Usage may be unreported')
                return json.dumps(event['structured_output']), usage
