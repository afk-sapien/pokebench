"""Provider schemas and controller execution share the same Gen 1 contract."""
import copy

import pytest
from jsonschema import Draft202012Validator

from pokeagent_bench.core import Limits
from pokeagent_bench.gameplay_commands import execute, validate
from pokeagent_bench.gameplay_contract import COMMANDS, action_schema
from test_gameplay import setup


EXAMPLES = {
    "move": ("right", 8),
    "interact": ("", 1),
    "choose": ("YES", 1),
    "use_move": ("4", 1),
    "use_item": ("Full Restore:1", 1),
    "switch_pokemon": ("6", 1),
    "press": ("a", 1),
    "wait": ("", 60),
    "inspect": ("memory", 1),
    "advance_dialogue": ("", 1),
}


def request(kind, argument, count=1):
    return {"command": kind, "argument": argument, "count": count}


def test_all_commands_have_valid_schema_and_examples():
    limits = Limits(max_action_frames=60)
    schema = action_schema(limits)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    assert set(EXAMPLES) == set(COMMANDS)
    assert {branch["properties"]["command"]["enum"][0] for branch in schema["anyOf"]} == set(COMMANDS)
    for kind, (argument, count) in EXAMPLES.items():
        command = request(kind, argument, count)
        validator.validate(command)
        assert validate(command, limits) == command


@pytest.mark.parametrize("kind", COMMANDS)
def test_schema_and_runtime_agree_on_counts_and_argument_types(kind):
    limits = Limits(max_action_frames=60)
    schema = Draft202012Validator(action_schema(limits))
    argument = EXAMPLES[kind][0]
    for count in (-1, 0, 1, 1.0, 1.5, 2, 8, 9, 60, 60.0, 61, 600, True, "1", None):
        for value in (argument, None, 1, [], {}):
            command = request(kind, value, count)
            valid = schema.is_valid(command)
            try:
                validate(command, limits)
            except ValueError:
                assert not valid, command
            else:
                assert valid, command


@pytest.mark.parametrize("command", [
    request("press", "a", 2),
    request("move", "north"),
    request("wait", "", 61),
    request("choose", "   "),
    request("choose", "A" * 81),
    request("use_move", "5"),
    request("use_item", "Revive:7"),
    request("use_item", "TM01:1"),
    request("use_item", "Revive:1:2"),
    request("switch_pokemon", "0"),
    request("inspect", "evaluator"),
    request("advance_dialogue", "yes"),
    request("unknown", ""),
    request([], ""),
    {"command": "press", "argument": "a"},
    {**request("press", "a"), "extra": True},
])
def test_invalid_commands_cannot_mutate_game_or_history(tmp_path, engine, command):
    session = setup(tmp_path, engine)
    try:
        before = bytes(engine.memory)
        history = copy.deepcopy(session.gameplay_memory)
        with pytest.raises(ValueError, match="No action executed"):
            execute(session, "invalid", command)
        assert not engine.inputs
        assert session.frame == 0
        assert bytes(engine.memory) == before
        assert session.gameplay_memory == history
        assert not session.gameplay_operations
        assert not Draft202012Validator(action_schema(session.limits)).is_valid(command)
    finally:
        session.close()


@pytest.mark.parametrize("command,message", [
    (request("press", "a", 2), "press.count must be 1"),
    (request("wait", "", 61), "wait.count must be an integer from 1 to 60"),
    (request("move", "up", True), "move.count must be an integer"),
    (request("switch_pokemon", "8"), "switch_pokemon.argument must be a party slot string from 1 to 6"),
    (request("inspect", "secret"), "inspect.argument must be one of party, bag, storage, map or memory"),
    ({"command": "press", "argument": "a"}, "missing count"),
])
def test_rejections_explain_the_actual_constraint(command, message):
    with pytest.raises(ValueError, match=message):
        validate(command, Limits(max_action_frames=60))


@pytest.mark.parametrize("argument", ["Full Restore:1", "FULL_RESTORE:6", "full restore: 2", "Elixir:2", "Elixer:3", "Max Revive:3"])
def test_supported_item_spellings_have_schema_controller_parity(argument):
    command = request("use_item", argument)
    limits = Limits()
    Draft202012Validator(action_schema(limits)).validate(command)
    validate(command, limits)


@pytest.mark.parametrize("maximum", [60, 120, 600])
def test_both_provider_decision_schemas_use_the_same_real_frame_limit(maximum):
    from pokeagent_bench.bounded_provider import BoundedGameplayProvider
    from pokeagent_bench.claude_provider import ClaudeCodeProvider

    limits = Limits(max_action_frames=maximum)
    schemas = []
    for cls in (BoundedGameplayProvider, ClaudeCodeProvider):
        provider = object.__new__(cls)
        provider.response_contract = "compact"
        schema = provider.decision_schema(limits)
        Draft202012Validator.check_schema(schema)
        schemas.append(schema)
        validator = Draft202012Validator(schema)
        # Optional metadata may be absent, without relaxing controller bounds.
        validator.validate({"actions": [request("wait", "", maximum)]})
        validator.validate({"actions": [], "look_back": 1})
        assert not validator.is_valid({"actions": [request("wait", "", maximum + 1)]})
        assert not validator.is_valid({"actions": [request("press", "a", 2)]})
        assert not validator.is_valid({"actions": [], "look_back": True})
        assert not validator.is_valid({"actions": [request("press", "a"), request("press", "b")]})
    assert schemas[0] == schemas[1]


def test_integral_json_count_is_normalized_without_mutating_the_request():
    limits = Limits()
    command = request("press", "a", 1.0)
    Draft202012Validator(action_schema(limits)).validate(command)
    normalized = validate(command, limits)
    assert normalized == request("press", "a", 1)
    assert type(normalized["count"]) is int
    assert type(command["count"]) is float


@pytest.mark.parametrize("count", [True, False, 1.5, float("inf"), float("-inf"), float("nan")])
def test_nonintegral_or_nonfinite_counts_are_never_normalized(count):
    with pytest.raises(ValueError, match="count must be an integer"):
        validate(request("press", "a", count), Limits())
