"""Metered response repair without executing malformed controller requests."""
from copy import deepcopy
import json

from jsonschema import Draft202012Validator

OPTIONAL = ('notes', 'goal_plan', 'look_back')
ADAPTER = 'claude-interface-v4'


def wire_schema(schema):
    result = deepcopy(schema)
    result['required'] = [key for key in result['required'] if key not in OPTIONAL]
    return result


def normalize(value, schema):
    if not isinstance(value, dict):
        raise ValueError('Return a JSON decision object')
    value = deepcopy(value)
    for key in OPTIONAL:
        value.setdefault(key, None)
    errors = sorted(Draft202012Validator(schema).iter_errors(value), key=lambda e: str(list(e.path)))
    if errors:
        error = errors[0]
        path = '.'.join(map(str, error.path)) or 'decision'
        raise ValueError(f'Invalid {path}: violates {error.validator}')
    return value


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
        commands = set(self.schema['properties']['actions']['items']['properties']['command']['enum'])
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
                value = normalize(event.get('structured_output'), self.schema)
            except ValueError as error:
                feedback = ('Response format error. No action was executed. ' + str(error) +
                    '. Return the decision through StructuredOutput with actions as an array. '
                    'Game commands are values inside actions, not callable tools. '
                    'Omitted notes, goal_plan and look_back mean null. Use a full goal_plan on the first decision.')
                self.interface_feedback = feedback
                self.interface_record.update(correction_needed=True, feedback=feedback)
                # Existing runner validation meters this decision, applies its three-error
                # limit and checks the remaining token budget before asking again.
                value = {'actions': [], 'notes': None, 'goal_plan': None, 'look_back': None,
                         'interface_error': 'Response format correction required'}
            else:
                self.interface_feedback = None
            return json.dumps(value), usage

    cls.interface_adapter = ADAPTER
    cls.__init__ = initialize
    cls._start = start
    cls.decide = decide
    cls._complete = complete
