"""Spending guards for revisiting known locations and for long stretches without a milestone."""


def milestone_gap(awarded, tokens, decision):
    """Tokens spent since the latest verified milestone, read from the award's own token stamp.

    The awards live in the evaluator checkpoint, so the count carries across resumes and extension chunks.
    """
    stamps = [(row.get("tokens", 0), row.get("decision", 0)) for row in awarded.values()]
    last_tokens, last_decision = max(stamps, default=(0, 0))
    return {"protocol": "milestone-token-budget-v1", "checked_decision": decision,
            "tokens_without_milestone": tokens - last_tokens, "last_milestone_tokens": last_tokens,
            "last_milestone_decision": last_decision, "milestones": len(awarded)}


def initial():
    return {"seen_positions": set(), "seen_achievements": set(), "last_progress_tokens": 0,
            "last_progress_decision": 0, "last_reason": "initial"}


def update(state, location, achievements, tokens, decision):
    position = tuple(location[key] for key in ("map_id", "x", "y"))
    awards = set(achievements)
    new_position = position not in state["seen_positions"]
    new_award = bool(awards - state["seen_achievements"])
    state["seen_positions"].add(position)
    state["seen_achievements"].update(awards)
    if new_position or new_award:
        state.update(last_progress_tokens=tokens, last_progress_decision=decision,
                     last_reason="new_location" if new_position else "verified_milestone")
    return {"protocol": "novel-location-token-budget-v1", "checked_decision": decision,
            "tokens_without_progress": tokens - state["last_progress_tokens"],
            "last_progress_decision": state["last_progress_decision"], "last_reason": state["last_reason"],
            "unique_locations": len(state["seen_positions"])}
