from copy import deepcopy

from conftest import blank_evidence
from pokeagent_bench.scoring import Evaluator


def test_badge_requires_leader_flag_and_two_frames():
    state = blank_evidence()
    evaluator = Evaluator(deepcopy(state))
    state["badges"] = 1
    assert evaluator.observe(state, 1, 0) == []
    assert evaluator.observe(state, 2, 0) == []
    state["gym_flags"][0] = True
    assert evaluator.observe(state, 3, 0) == []
    assert evaluator.observe(state, 4, 1)[0]["points"] == 75
    assert evaluator.observe(state, 5, 1) == []
    assert evaluator.score == 75


def test_transient_and_initial_achievements_do_not_score():
    initial = blank_evidence()
    initial["badges"] = 1
    initial["gym_flags"][0] = True
    evaluator = Evaluator(deepcopy(initial))
    evaluator.observe(initial, 1, 0)
    evaluator.observe(initial, 2, 0)
    assert evaluator.score == 0
    initial["elite"]["Lorelei"] = True
    evaluator.observe(initial, 3, 0)
    initial["elite"]["Lorelei"] = False
    evaluator.observe(initial, 4, 0)
    assert evaluator.score == 0


def test_campaign_total_and_no_repeat_farming():
    initial = blank_evidence()
    evaluator = Evaluator(initial)
    state = deepcopy(initial)
    state.update(badges=255, gym_flags=[True] * 8, champion=True, hall_of_fame=1, map_id=118)
    state["elite"] = {name: True for name in state["elite"]}
    evaluator.observe(state, 100, 10)
    awards = evaluator.observe(state, 101, 11)
    assert len(awards) == 13
    assert evaluator.score == 1000
    assert evaluator.complete("campaign")
    evaluator.observe(initial, 102, 12)
    evaluator.observe(state, 103, 13)
    evaluator.observe(state, 104, 14)
    assert evaluator.score == 1000


def test_hall_room_without_champion_and_registration_does_not_finish():
    state = blank_evidence()
    evaluator = Evaluator(deepcopy(state))
    state["map_id"] = 118
    state["champion"] = True
    evaluator.observe(state, 1, 0)
    evaluator.observe(state, 2, 0)
    assert not evaluator.complete("campaign")
    state["hall_of_fame"] = 1
    state["valid"] = False
    evaluator.observe(state, 3, 0)
    evaluator.observe(state, 4, 0)
    assert evaluator.score == 0
