from copy import deepcopy

from pokeagent_bench.core import encoded
from pokeagent_bench.working_memory import record, recall


def result(text="Those are balls", x=6):
    return {"request": {"command": "interact", "argument": "", "count": 1},
            "position_before": {"map_id": 40, "x": x, "y": 4, "secret": "HIDDEN"},
            "position_after": {"map_id": 40, "x": x, "y": 4}, "outcome": "executed",
            "dialogue": {"pages": [text]}, "private": "HIDDEN"}


def test_unique_clue_survives_repeated_dialogue_and_fifty_decision_window():
    history = {}
    screen = {"kind": "overworld", "private": "HIDDEN"}
    record(history, 1, result("Gramps isn't around!", x=4), "up", screen)
    for i in range(2, 102):
        record(history, i, result(), "up", screen)
    view = recall(history, 40)
    assert len(view["recent_decisions"]) == 50
    assert view["recent_decisions"][0]["decision"] == 52
    assert len(view["encounters"]) == 2
    assert view["encounters"][0]["text"] == "Gramps isn't around!"
    assert view["repeated_results"][0]["count"] == 100
    assert b"HIDDEN" not in encoded(view)
    assert b"starter" not in encoded(view)
    view["encounters"].clear()
    assert len(recall(history, 40)["encounters"]) == 2


def test_different_outcomes_and_facing_do_not_count_as_same_result():
    history = {}
    for i, (text, facing) in enumerate((("Hello", "up"), ("Goodbye", "up"), ("Hello", "left")), 1):
        record(history, i, result(text), facing, {"kind": "overworld"})
    assert not recall(history, 40)["repeated_results"]


def test_memory_bounds_and_utf8_truncation_are_explicit():
    history = {}
    for i in range(150):
        record(history, i, result(str(i) + "é" * 2000), "up", {})
    state = history["working"]
    assert len(state["decisions"]) == 50
    assert len(state["encounters"]) == 64
    assert len(state["repetitions"]) == 128
    view = recall(history, 40)
    assert view["omitted_encounters"] > 0
    assert all(e["truncated"] for e in view["encounters"])
    assert sum(len(encoded(e)) for e in view["encounters"]) <= 6000
    assert len(recall(history, 40, inspect=True)["encounters"]) > len(view["encounters"])


def test_multiple_commands_in_one_decision_group_together_and_empty_recall_is_read_only():
    history = {}
    before = deepcopy(history)
    assert recall(history, 40)["recent_decisions"] == []
    assert history == before
    record(history, 1, result(), "up", {})
    record(history, 1, result(x=7), "up", {})
    assert len(recall(history, 40)["recent_decisions"]) == 1
    assert len(recall(history, 40)["recent_decisions"][0]["commands"]) == 2
