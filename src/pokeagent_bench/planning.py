"""Persistent agent-authored goals, separate from observations and scratch notes."""
from copy import deepcopy

FIELDS = ("goal", "evidence", "done_when", "revision_reason")
SCHEMA = {"anyOf": [{"type": "null"}, {"type": "object", "additionalProperties": False,
          "properties": {key: {"type": "string", "minLength": 1, "maxLength": 400} for key in FIELDS},
          "required": list(FIELDS)}]}


def validate(value, existing):
    if value is None:
        if existing is None:
            raise ValueError("Set an initial goal_plan with evidence and a completion condition")
        return None
    if not isinstance(value, dict) or set(value) != set(FIELDS):
        raise ValueError("goal_plan needs goal, evidence, done_when and revision_reason")
    if any(not isinstance(value[k], str) or not value[k].strip() or len(value[k]) > 400 for k in FIELDS):
        raise ValueError("Each goal_plan field must contain 1 to 400 characters")
    if sum(len(value[k].encode()) for k in FIELDS) > 2048:
        raise ValueError("goal_plan exceeds 2048 UTF-8 bytes")
    normalized = {key: value[key].strip() for key in FIELDS}
    placeholders = {"", "null", "none", "na", "unchanged", "same", "keep"}
    if any("".join(char for char in normalized[key].casefold() if char.isalnum()) in placeholders for key in FIELDS):
        raise ValueError("Use JSON null to retain the plan. Plan fields need substantive text")
    if existing is not None and all(normalized[key] == existing[key] for key in FIELDS if key != "revision_reason"):
        return None
    return normalized


def commit(session, plan):
    if plan is None:
        return
    history = session.gameplay_memory
    previous = history.get("agent_plan")
    if previous is not None:
        revisions = history.setdefault("plan_revisions", [])
        revisions.append({"decision": session.current_decision, "previous_goal": previous["goal"],
                          "new_goal": plan["goal"], "reason": plan["revision_reason"]})
        del revisions[:-4]
    history["agent_plan"] = {**deepcopy(plan), "set_at_decision": session.current_decision}
    session.audit_memory("agent_plan", history["agent_plan"])
