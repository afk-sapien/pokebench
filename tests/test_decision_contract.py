import json
import pytest

from pokeagent_bench.core import Limits
from pokeagent_bench.decision_contract import SPENT, parse_response, rejection
from pokeagent_bench.gameplay_provider import GameplayCodexProvider


def schema():
    provider = object.__new__(GameplayCodexProvider)
    provider.response_contract = 'simple'
    return provider.decision_schema(Limits())


@pytest.mark.parametrize('metadata', [{}, {'look_back': 1.0}, {'notes': None, 'goal_plan': None}])
def test_optional_metadata_and_integral_numbers_have_shared_semantics(metadata):
    value = {'actions': [{'command': 'press', 'argument': 'a', 'count': 1.0}], **metadata}
    decision, look_back, error = parse_response(json.dumps(value), schema(), Limits())
    assert error is None
    assert decision['actions'][0]['count'] == 1
    assert type(decision['actions'][0]['count']) is int
    assert look_back == (1 if 'look_back' in metadata else None)


def test_notes_limit_and_concrete_feedback_are_provider_neutral():
    value = {'actions': [{'command': 'press', 'argument': 'a', 'count': 1}], 'notes': 'x'*2049}
    decision, _, error = parse_response(json.dumps(value), schema(), Limits())
    assert 'notes' in error and 'maxLength' in error
    assert decision['actions'] == []
    rejection = {'actions': [], 'interface_error': 'press.count must be 1'}
    decision, _, error = parse_response(json.dumps(rejection), schema(), Limits())
    assert 'press.count must be 1' in decision['interface_error']


def test_empty_actions_require_screenshot_recall():
    decision, _, error = parse_response('{"actions": []}', schema(), Limits())
    assert error == decision['interface_error'] == (
        'No action was executed and this still used one decision. Empty actions do nothing. '
        'Send at least one controller action or request look_back from 1 to 8.')
    assert decision['actions'] == []
    decision, look_back, error = parse_response('{"actions": [], "look_back": 1}', schema(), Limits())
    assert error is None and look_back == 1


def test_a_rejected_command_says_once_that_nothing_ran_and_a_decision_was_used():
    value = {'actions': [{'command': 'fly', 'argument': 'a', 'count': 1}]}
    _, _, error = parse_response(json.dumps(value), schema(), Limits())
    assert error.startswith(SPENT + ' Unknown command.')
    assert error.count('No action') == 1 and error.endswith('.') and '..' not in error
    assert rejection(error) == error  # the runner adds nothing to a finished message


def test_codex_wire_schema_has_required_nullable_metadata_without_changing_semantics():
    from jsonschema import Draft202012Validator
    from pokeagent_bench.decision_contract import wire_schema
    canonical = schema()
    wire = wire_schema(canonical, 'codex')
    assert set(wire['required']) == set(wire['properties'])
    assert canonical['required'] == ['actions']
    value = {'actions': [{'command': 'press', 'argument': 'a', 'count': 1}],
             'notes': None, 'goal_plan': None, 'look_back': None}
    assert Draft202012Validator(wire).is_valid(value)
    assert wire_schema(canonical, 'claude-code') == canonical
