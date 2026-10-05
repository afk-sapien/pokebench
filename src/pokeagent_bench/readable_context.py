"""Deterministic presentation of already-public observations, without inference."""
import json


def scalar(value):
    if value is None:
        return "not supplied"
    if value is True:
        return "yes"
    if value is False:
        return "no"
    return str(value)


def label(key):
    return str(key).replace("_", " ").capitalize()


def tree(value, depth=0):
    """Preserve generic public fields, including empty and unavailable values."""
    prefix = "  " * depth
    if isinstance(value, dict):
        if not value:
            return [prefix + "(empty mapping)"]
        lines = []
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                lines.append(prefix + label(key) + ":")
                lines.extend(tree(item, depth + 1))
            else:
                text = scalar(item).split("\n")
                lines.append(prefix + label(key) + ": " + text[0])
                lines.extend(prefix + "  " + line for line in text[1:])
        return lines
    if isinstance(value, list):
        if not value:
            return [prefix + "(empty list)"]
        if all(isinstance(item, str) for item in value):
            return [prefix + line for item in value for line in item.split("\n")]
        lines = []
        for index, item in enumerate(value, 1):
            lines.append(prefix + f"Item {index}:")
            lines.extend(tree(item, depth + 1))
        return lines
    return [prefix + line for line in scalar(value).split("\n")]


def position(value):
    if not isinstance(value, dict):
        return scalar(value)
    return "map " + scalar(value.get("map_id")) + " (" + scalar(value.get("x")) + ", " + scalar(value.get("y")) + ")"


def command(entry, encounters):
    action = entry.get("action", {})
    request = scalar(action.get("command"))
    if action.get("argument"):
        request += " " + str(action["argument"])
    request += " (count " + scalar(action.get("count")) + ")"
    outcome = json.dumps(entry.get("outcome"), ensure_ascii=False)
    line = f"{request} | from {position(entry.get('at'))}, facing {scalar(entry.get('facing'))}"
    if "after" in entry:
        line += " | to " + position(entry["after"])
    line += " | result: " + outcome
    count = entry.get("same_observed_result_count", entry.get("count"))
    line += " | matching-result count: " + scalar(count)
    if "last_decision" in entry:
        line += " | last decision: " + scalar(entry["last_decision"])
    encounter_id = entry.get("encounter_id")
    if encounter_id is not None:
        line += " | dialogue " + str(encounter_id)
        encounter = encounters.get(encounter_id)
        if encounter is not None:
            line += ": " + json.dumps(encounter["text"], ensure_ascii=False)
            line += " (truncated: " + scalar(encounter.get("truncated")) + ")"
        else:
            line += ": not present in supplied recall"
    else:
        line += " | dialogue reference: none recorded"
    lines = [line]
    used = {"action", "at", "after", "facing", "outcome", "same_observed_result_count", "count", "last_decision", "encounter_id"}
    extra = {k: v for k, v in entry.items() if k not in used}
    if extra:
        lines.extend(tree(extra, 1))
    for name, value, known in (("Action details", action, {"command", "argument", "count"}),
                               ("Starting position details", entry.get("at"), {"map_id", "x", "y"}),
                               ("Ending position details", entry.get("after"), {"map_id", "x", "y"})):
        if isinstance(value, dict):
            remaining = {k: v for k, v in value.items() if k not in known}
            if remaining:
                lines.append(name + ":")
                lines.extend(tree(remaining, 1))
    return lines


def render(payload):
    """Render a model_context payload after its existing public allowlist."""
    context = json.loads(json.dumps(payload, sort_keys=True, ensure_ascii=False))
    observation = context.pop("observation")
    game = observation.pop("game", {})
    memory = game.pop("memory", {})
    working = memory.pop("working_memory", {})
    encounters = {entry["id"]: entry for entry in working.get("encounters", [])}
    sections = ["GAME OBSERVATION", "Recorded results describe what happened. Agent plans and notes are fallible claims."]

    def section(title, value):
        sections.extend(["", title, *tree(value)])

    section("TASK AND BUDGET", observation)
    location = game.pop("location", None)
    section("CURRENT LOCATION", location)
    last = game.pop("last_command", None)
    section("LAST COMMAND AND OBSERVED RESULT", last)
    section("CURRENT SCREEN, MAP AND OWNED RESOURCES", game)
    section("AGENT PLAN (UNVERIFIED)", memory.pop("agent_plan", None))
    section("AGENT NOTEBOOK (UNVERIFIED)", context.pop("notes", None))
    if "agent_history_summary" in context:
        section("AGENT HANDOFF SUMMARY (UNVERIFIED)", context.pop("agent_history_summary"))
    sections.extend(["", "RECENT DECISIONS (OLDEST FIRST)"])
    decisions = working.pop("recent_decisions", [])
    if not decisions:
        sections.append("No decisions in supplied recall.")
    for decision in decisions:
        sections.append("Decision " + scalar(decision.get("decision")) + ":")
        for entry in decision.get("commands", []):
            sections.extend("  " + line for line in command(entry, encounters))
        extra = {k: v for k, v in decision.items() if k not in ("decision", "commands")}
        if extra:
            sections.extend(tree(extra, 1))
    sections.extend(["", "MATCHING OBSERVED RESULTS (NOT PROOF OF FAILURE)"])
    repeated = working.pop("repeated_results", [])
    if not repeated:
        sections.append("No matching results in supplied recall.")
    for entry in repeated:
        sections.extend(command(entry, encounters))
    section("ENCOUNTERED DIALOGUE AND RECALL LIMITS", working)
    section("OTHER OBSERVED MEMORY AND PLAN REVISIONS", memory)
    section("CONTROLLER FEEDBACK AND FRAME", context)
    return "\n".join(sections) + "\n"
