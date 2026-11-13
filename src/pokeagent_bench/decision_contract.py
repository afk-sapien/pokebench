"""Provider-neutral gameplay response validation and metered rejection feedback."""
from copy import deepcopy
import json

from jsonschema import Draft202012Validator

from .core import Limits
from .gameplay_contract import validate_command

OPTIONAL = ('notes', 'goal_plan', 'look_back')
# Every rejected response is a metered model call, so its feedback says so first.
SPENT = 'No action was executed and this still used one decision.'
NOTHING_RAN = ('No action was executed.', 'No action executed.', 'No action executed')


def reason(text):
    """The rejection reason alone, without a trailing note that nothing ran."""
    text = ' '.join(str(text).split())
    for tail in NOTHING_RAN:
        if text.endswith(tail):
            text = text[:-len(tail)]
            break
    return text.rstrip(' .')


def rejection(text):
    """Feedback for a rejected response, led by the decision it cost."""
    text = ' '.join(str(text).split())
    return text if SPENT in text else f'{SPENT} {reason(text)}.'


def normalize(value, schema, limits=None):
    if not isinstance(value, dict):
        raise ValueError('Return a JSON decision object')
    value = deepcopy(value)
    for key in OPTIONAL:
        value.setdefault(key, None)
    if isinstance(value.get('actions'), list):
        value['actions'] = [validate_command(item, limits or Limits(max_action_frames=600))
                            for item in value['actions']]
    if type(value['look_back']) is float and value['look_back'].is_integer():
        value['look_back'] = int(value['look_back'])
    errors = sorted(Draft202012Validator(schema).iter_errors(value), key=lambda e: str(list(e.path)))
    if errors:
        error = errors[0]
        path = '.'.join(map(str, error.path)) or 'decision'
        raise ValueError(f'Invalid {path}: violates {error.validator}')
    if not value['actions'] and value['look_back'] is None:
        raise ValueError('Empty actions do nothing. Send at least one controller action or request look_back from 1 to 8')
    return value


def parse_response(message, schema, limits):
    """Return a rejected zero-action decision while preserving caller usage."""
    try:
        response = json.loads(message)
        if isinstance(response, dict) and 'interface_error' in response:
            error = response['interface_error']
            raise ValueError(error if isinstance(error, str) else 'Invalid response format')
        response = normalize(response, schema, limits)
        look_back = response.pop('look_back')
        return response, look_back, None
    except (ValueError, TypeError) as error:
        text = 'Return valid JSON with an actions array' if isinstance(error, json.JSONDecodeError) else str(error)
        text = rejection(' '.join(text.split())[:450])
        return {'actions': [], 'notes': None, 'goal_plan': None, 'interface_error': text}, None, text


def wire_schema(schema, provider):
    """Codex strict decoding needs every key, while null retains optional metadata."""
    result = deepcopy(schema)
    if provider == 'codex':
        result['required'] = list(result['properties'])
    return result
