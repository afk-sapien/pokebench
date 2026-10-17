"""Descriptive outcome labels derived from existing termination reasons."""

BUDGET_STOPS = frozenset({
    "token_budget", "model_call_budget", "wall_budget", "frame_budget", "action_budget",
    "observation_stagnation_budget", "area_token_budget", "loop_token_budget",
})
INFRASTRUCTURE_STOPS = frozenset({
    "provider_error", "infrastructure_error", "usage_unavailable", "observation_budget",
})
LABELS = {
    "success": "Completed",
    "gameplay_loss": "Battle lost",
    "task_failure": "Task constraints violated",
    "submitted": "Preparation submitted",
    "budget_exhausted": "Budget exhausted",
    "interface_failure": "Invalid model response",
    "infrastructure_failure": "Infrastructure failure",
    "interrupted": "Interrupted",
    "running": "Running",
    "pending": "Pending",
    "paused": "Paused",
    "unknown": "Outcome unavailable",
}


def outcome_category(stop_reason, *, state=None, completed=None):
    """Classify without changing whether an attempt is scored or counted."""
    if stop_reason == "completed":
        return "success"
    if stop_reason == "submitted":
        return "submitted"
    if stop_reason in ("challenge_failed", "preparation_action_failed"):
        return "task_failure"
    if stop_reason == "battle_loss":
        return "gameplay_loss"
    if stop_reason == "invalid_model_response":
        return "interface_failure"
    if stop_reason in BUDGET_STOPS:
        return "budget_exhausted"
    if stop_reason in INFRASTRUCTURE_STOPS:
        return "infrastructure_failure"
    if stop_reason in ("interrupted", "paused"):
        return stop_reason
    if stop_reason:
        return "unknown"
    if state in ("running", "pending", "paused"):
        return state
    if state == "error":
        return "infrastructure_failure"
    if state == "finished" and completed is True:
        return "success"
    return "unknown"


def outcome_label(category):
    return LABELS.get(category, LABELS["unknown"])
