"""One explicit Gen 1 action contract for providers and controller validation."""
import re

from .core import BUTTONS

COMMANDS = (
    "move", "interact", "choose", "use_move", "use_item", "switch_pokemon",
    "press", "wait", "inspect", "advance_dialogue",
)


def _rules(limits):
    from .menu_shortcuts import ITEMS

    # Documented item names accept normal casing, spaces, underscores and hyphens.
    names = []
    for name in sorted(ITEMS):
        words = re.sub(r"^(FULL|SUPER|HYPER|MAX)(.+)$", r"\1 \2", name)
        words = re.sub(r"(BURN|ICE|PARLYZ)(HEAL)$", r"\1 \2", words)
        names.append("[ _-]*".join("".join("[EeÉé]" if letter == "E" else
                     f"[{letter}{letter.lower()}]" for letter in word) for word in words.split()))
    item_pattern = r"^\s*(?:" + "|".join(names) + r")\s*:\s*[1-6]\s*$"
    rules = {
        "move": ({"enum": ["up", "down", "left", "right"]}, 8, "a direction: up, down, left or right"),
        "interact": ({"enum": [""]}, 1, "an empty string"),
        "choose": ({"minLength": 1, "maxLength": 80, "pattern": r"\S"}, 1,
                   "nonblank visible option text, at most 80 characters"),
        "use_move": ({"enum": list("1234")}, 1, "a move slot string from 1 to 4"),
        "use_item": ({"pattern": item_pattern}, 1,
                     "a supported restorative item and party slot, such as Full Restore:1"),
        "switch_pokemon": ({"enum": list("123456")}, 1, "a party slot string from 1 to 6"),
        "press": ({"enum": list(BUTTONS)}, 1, "a button: " + ", ".join(BUTTONS)),
        "wait": ({"enum": [""]}, limits.max_action_frames, "an empty string"),
        "inspect": ({"enum": ["party", "bag", "storage", "map", "memory"]}, 1,
                    "one of party, bag, storage, map or memory"),
        "advance_dialogue": ({"enum": [""]}, 1, "an empty string"),
    }
    return rules


def action_schema(limits, policy=None):
    """Use a discriminated union so argument and count follow the chosen command."""
    from .action_policy import ASSISTED, commands
    allowed = commands(policy or ASSISTED)
    variants = []
    for kind, (argument, maximum, description) in _rules(limits).items():
        if kind not in allowed:
            continue
        count = {"type": "integer", "enum": [1]} if maximum == 1 else {
            "type": "integer", "minimum": 1, "maximum": maximum,
        }
        variants.append({
            "type": "object", "additionalProperties": False,
            "properties": {
                "command": {"type": "string", "enum": [kind]},
                "argument": {"type": "string", **argument, "description": description},
                "count": count,
            },
            "required": ["command", "argument", "count"],
        })
    return {"anyOf": variants}


def validate_command(command, limits, policy=None):
    """Reject malformed requests before reading state or sending any controller input."""
    def reject(message):
        raise ValueError(message + ". No action executed.")

    if not isinstance(command, dict):
        reject("Action must be an object with command, argument and count")
    fields = {"command", "argument", "count"}
    if set(command) != fields:
        missing = ", ".join(sorted(fields - command.keys()))
        extra = ", ".join(sorted(str(key) for key in command.keys() - fields))
        details = []
        if missing:
            details.append("missing " + missing)
        if extra:
            details.append("unexpected " + extra)
        reject("Action fields invalid: " + ", ".join(details))
    kind, argument, count = command["command"], command["argument"], command["count"]
    rules = _rules(limits)
    if not isinstance(kind, str) or kind not in rules:
        reject("Unknown command. Choose one of " + ", ".join(COMMANDS))
    from .action_policy import ASSISTED, commands
    allowed = commands(policy or ASSISTED)
    if kind not in allowed:
        reject(f"{kind} is disabled by {policy}. Allowed commands: " + ", ".join(allowed))
    arg_rule, maximum, description = rules[kind]
    # JSON Schema treats finite integral numbers such as 1.0 as integers.
    if type(count) is float and count.is_integer():
        count = int(count)
    if type(count) is not int:
        reject(f"{kind}.count must be an integer")
    if not 1 <= count <= maximum:
        expected = "1" if maximum == 1 else f"an integer from 1 to {maximum}"
        reject(f"{kind}.count must be {expected}")
    if not isinstance(argument, str):
        reject(f"{kind}.argument must be a string containing {description}")
    valid = (
        ("enum" not in arg_rule or argument in arg_rule["enum"])
        and len(argument) >= arg_rule.get("minLength", 0)
        and ("maxLength" not in arg_rule or len(argument) <= arg_rule["maxLength"])
        and ("pattern" not in arg_rule or re.search(arg_rule["pattern"], argument) is not None)
    )
    if not valid:
        reject(f"{kind}.argument must be {description}")
    return {**command, "count": count}
