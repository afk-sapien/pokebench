"""Metered response repair without executing malformed controller requests."""
from copy import deepcopy
import json

from .decision_contract import OPTIONAL, normalize

ADAPTER = 'claude-interface-v7'


def wire_schema(schema):
    result = deepcopy(schema)
    result['required'] = [key for key in result['required'] if key not in OPTIONAL]
    return result


def install(module):
    """Install on a provider class, including checksum-pinned frozen runtimes."""
    cls = module.ClaudeCodeProvider
    if getattr(cls, 'interface_adapter', None) == ADAPTER:
        return
    original_start = cls._start
    original_decide = cls.decide
    original_init = cls.__init__

    def initialize(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self.config_identity.update(response_adapter=ADAPTER,
            optional_metadata='omission-means-null', response_correction='metered-next-decision',
            max_consecutive_invalid_decisions=3)

    def start(self, deadline):
        original = self.schema
        self.schema = wire_schema(original)
        try:
            original_start(self, deadline)
        finally:
            self.schema = original

    def decide(self, *args, **kwargs):
        decision, usage, record = original_decide(self, *args, **kwargs)
        record['response_interface'] = self.interface_record
        return decision, usage, record

    def complete(self, method, params, deadline):
        content = []
        for item in params['input']:
            if item['type'] == 'text':
                content.append({'type': 'text', 'text': item['text']})
            else:
                content.append({'type': 'image', 'source': {'type': 'base64',
                    'media_type': 'image/png', 'data': item['url'].split(',', 1)[1]}})
        if getattr(self, 'interface_feedback', None):
            content.append({'type': 'text', 'text': self.interface_feedback})
        self.server.send({'type': 'user', 'message': {'role': 'user', 'content': content}})
        native_commands = []
        from .gameplay_contract import COMMANDS
        commands = set(COMMANDS)
        while True:
            event = self.server.event(deadline)
            kind = event.get('type')
            if kind in ('transport_error', 'transport_closed'):
                raise module.ProviderError('Claude transport ended. Usage may be unreported')
            if kind == 'system' and event.get('subtype') == 'init':
                if event.get('model') != self.model or event.get('mcp_servers') or set(event.get('tools', [])) != {'StructuredOutput'}:
                    raise module.ProviderError('Claude model or tool isolation mismatch')
                if self.thread_id is not None and event['session_id'] != self.thread_id:
                    raise module.ProviderError('Claude resumed a different session')
                self.thread_id = event['session_id']
            if kind == 'system' and event.get('subtype') == 'compact_boundary':
                raise module.ProviderError('Unexpected automatic compaction invalidates this trial')
            if kind == 'assistant':
                message = event['message']
                if message.get('model') == '<synthetic>':
                    quota = event.get('quotaLimits') or event.get('apiErrorParams', {}).get('rate_limit_info') or {}
                    limited = event.get('apiError') == 'usage_limit_reached' or event.get('error') == 'rate_limit'
                    details = {'kind': 'subscription_limit' if limited else 'provider_error',
                               'provider_code': event.get('apiError'), 'status': event.get('apiErrorStatus'),
                               'resets_at': quota.get('resetsAt'), 'limit_type': quota.get('rateLimitType')}
                    raise module.ProviderError('Claude subscription usage limit reached' if limited
                                               else 'Claude returned a synthetic provider error', details=details)
                if message.get('model') != self.model:
                    raise module.ProviderError('Claude resolved a different model')
                for block in message.get('content', []):
                    if block.get('type') == 'tool_use' and block.get('name') != 'StructuredOutput':
                        name = block.get('name')
                        if name not in commands:
                            raise module.ProviderError('Claude attempted an outside tool')
                        # The CLI has no game tools. Never dispatch or translate this request.
                        native_commands.append(name)
            if kind != 'result':
                continue
            usage, self.total_usage = module.usage_delta(event.get('modelUsage', {}), self.model, self.total_usage)
            last = event.get('usage', {})
            self.context_tokens = sum(last.get(key, 0) for key in
                ('input_tokens', 'output_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens'))
            self.interface_record = {'adapter': ADAPTER, 'unavailable_game_tools': native_commands,
                                     'result_subtype': event.get('subtype'), 'correction_needed': False}
            recoverable = event.get('subtype') in ('success', 'error_max_structured_output_retries', 'error_max_turns')
            if not recoverable:
                raise module.ProviderError('Claude transport failed. Usage may be unreported')
            try:
                if event.get('is_error') or event.get('subtype') != 'success':
                    raise ValueError('No valid structured decision was returned')
                normalizer = getattr(self, 'response_normalizer', normalize)
                value = normalizer(event.get('structured_output'), self.schema, getattr(self, 'decision_limits', None))
            except ValueError as error:
                feedback = ('Response format error. No action was executed. ' + str(error) +
                    '. Return the decision through StructuredOutput with actions as an array. '
                    'Game commands are values inside actions, not callable tools. '
                    'Omitted notes, goal_plan and look_back mean null. Plans and notes are optional.')
                self.interface_feedback = feedback
                self.interface_record.update(correction_needed=True, feedback=feedback,
                    rejected_response=event.get('structured_output'))
                # Existing runner validation meters this decision, applies its three-error
                # limit and checks the remaining token budget before asking again.
                value = {'actions': [], 'notes': None, 'goal_plan': None, 'look_back': None,
                         'interface_error': feedback[:512]}
            else:
                self.interface_feedback = None
            return json.dumps(value), usage

    cls.interface_adapter = ADAPTER
    cls.__init__ = initialize
    cls._start = start
    cls.decide = decide
    cls._complete = complete
