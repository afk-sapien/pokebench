import pytest

from pokeagent_bench.outcomes import outcome_category, outcome_label


@pytest.mark.parametrize("reason,expected", [
    ("completed", "success"),
    ("battle_loss", "gameplay_loss"),
    ("invalid_model_response", "interface_failure"),
    ("token_budget", "budget_exhausted"),
    ("model_call_budget", "budget_exhausted"),
    ("wall_budget", "budget_exhausted"),
    ("observation_stagnation_budget", "budget_exhausted"),
    ("provider_error", "infrastructure_failure"),
    ("usage_unavailable", "infrastructure_failure"),
    ("observation_budget", "infrastructure_failure"),
    ("interrupted", "interrupted"),
    ("paused", "paused"),
    ("unknown_budget", "unknown"),
])
def test_explicit_termination_categories(reason, expected):
    assert outcome_category(reason) == expected
    assert outcome_label(expected)


def test_historical_missing_reason_does_not_invent_a_battle_loss():
    assert outcome_category(None, state="finished", completed=False) == "unknown"
    assert outcome_category(None, state="finished", completed=True) == "success"
    assert outcome_category(None, state="error") == "infrastructure_failure"
    assert outcome_category(None, state="pending") == "pending"
    assert outcome_category(None, state="running") == "running"
    assert outcome_category("new_reason", state="finished", completed=True) == "unknown"
    assert outcome_label("not-a-category") == "Outcome unavailable"


def test_new_session_status_and_result_share_category_without_changing_score(session):
    import json

    before = session.status()
    assert before["outcome_category"] == "running"
    session.finish("invalid_model_response")
    status = session.status()
    result = json.loads((session.output / "result.json").read_text())
    assert status["outcome_category"] == result["outcome_category"] == "interface_failure"
    assert status["score"] == before["score"]
    assert result["stop_reason"] == "invalid_model_response"
    assert result["completed"] is False
