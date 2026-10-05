"""Bounded recall of observed commands and dialogue, without inferred advice."""
from copy import deepcopy

from .core import digest, encoded

PROTOCOL = "observed-decision-memory-v2"


def clip(text, size):
    raw = str(text).encode()
    return raw[:size].decode("utf-8", errors="ignore"), len(raw) > size


def position(value):
    return {key: value[key] for key in ("map_id", "x", "y")}


def record(history, decision, result, facing, screen):
    """Call once after a new command executes, never on observation or retry."""
    state = history.setdefault("working", {"decisions": [], "encounters": {}, "repetitions": {}})
    before, after = position(result["position_before"]), position(result["position_after"])
    request = {key: result["request"][key] for key in ("command", "argument", "count")}
    pages = result.get("dialogue", {}).get("pages", [])
    text = "\n".join(dict.fromkeys(" ".join(page.split()) for page in pages if page.strip()))
    encounter = None
    if text:
        encounter = digest(encoded([before["map_id"], text]))[:16]
        entries = state["encounters"]
        if encounter not in entries:
            excerpt, truncated = clip(text, 2048)
            entries[encounter] = {"id": encounter, "map_id": before["map_id"],
                "first_decision": decision, "last_decision": decision, "count": 0,
                "text": excerpt, "truncated": truncated}
        entries[encounter]["last_decision"] = decision
        entries[encounter]["count"] += 1
        while len(entries) > 64:
            del entries[next(iter(entries))]
    outcome, _ = clip(result["outcome"], 240)
    # Text and menus are observed outcomes. Private battle state is never read.
    visible = {key: screen.get(key) for key in ("kind", "text", "visible_choices", "selected_text")}
    signature = digest(encoded([before, facing, request, after, outcome, text, visible]))
    repeats = state["repetitions"]
    previous = repeats.pop(signature, None)
    count = previous["count"] + 1 if previous else 1
    repeats[signature] = {"at": before, "facing": facing, "action": request,
        "outcome": outcome, "encounter_id": encounter, "count": count, "last_decision": decision}
    while len(repeats) > 128:
        del repeats[next(iter(repeats))]
    command = {"at": before, "facing": facing, "action": request, "after": after,
               "outcome": outcome, "encounter_id": encounter, "same_observed_result_count": count}
    decisions = state["decisions"]
    if not decisions or decisions[-1]["decision"] != decision:
        decisions.append({"decision": decision, "commands": []})
    decisions[-1]["commands"].append(command)
    del decisions[:-50]


def recall(history, map_id, *, inspect=False):
    state = history.get("working", {"decisions": [], "encounters": {}, "repetitions": {}})
    encounters = list(state["encounters"].values())
    referenced = {c["encounter_id"] for d in state["decisions"] for c in d["commands"]}
    # Prefer referenced and current-map conversations, without judging their meaning.
    ranked = sorted(encounters, key=lambda e: (e["id"] in referenced, e["map_id"] == map_id, e["first_decision"]), reverse=True)
    selected, remaining = [], 12000 if inspect else 6000
    for entry in ranked:
        cost = len(encoded(entry))
        if cost <= remaining:
            selected.append(entry)
            remaining -= cost
    repetitions = [row for row in state["repetitions"].values() if row["count"] > 1 and row["at"]["map_id"] == map_id]
    repetitions.sort(key=lambda row: (row["count"], row["last_decision"]), reverse=True)
    return deepcopy({"protocol": PROTOCOL, "recent_decisions": state["decisions"],
        "encounters": sorted(selected, key=lambda e: e["first_decision"]),
        "repeated_results": repetitions[:8], "retained_encounters": len(encounters),
        "omitted_encounters": len(encounters) - len(selected),
        "caveat": "Recorded observations, not advice. Repeated text is not proof of failure. Agent notes are separate hypotheses."})
