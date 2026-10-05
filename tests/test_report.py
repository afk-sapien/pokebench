from copy import deepcopy

from fastapi.testclient import TestClient

from pokeagent_bench.cli import execute, parser
from pokeagent_bench.dashboard import create_app
from pokeagent_bench.report import comparison_report, summarize


def trial(**changes):
    row = {"group": "same", "provider": "test", "model": "model-a", "state": "finished",
           "stop_reason": "action_budget", "completed": False, "score": 0, "wall_seconds": 30,
           "emulated_seconds": 10, "actions": 20,
           "usage": {"available": True, "calls": 2, "input_tokens": 100, "output_tokens": 20,
                     "estimated_cost_usd": None}}
    row.update(changes)
    return row


def test_summary_keeps_gameplay_metrics_separate_from_all_trial_spend():
    won = trial(completed=True, score=75, stop_reason="success", wall_seconds=10, actions=10)
    won["usage"]["estimated_cost_usd"] = 0.25
    error = trial(stop_reason="provider_error", score=75, wall_seconds=999, actions=999)
    error["usage"]["estimated_cost_usd"] = 0.5
    live = trial(state="running", stop_reason=None, wall_seconds=888, actions=888)
    result = summarize([won, trial(), error, live])[0]
    assert result["trials"] == 4
    assert result["evaluated"] == 2
    assert result["running"] == 1
    assert result["errors_or_interruptions"] == 1
    assert result["success_rate"] == 0.5
    assert result["mean_score"] == 37.5
    assert result["median_completion_wall_seconds"] == 10
    assert result["median_wall_seconds"] == 20
    assert result["median_emulated_seconds"] == 10
    assert result["median_actions"] == 15
    assert result["total_model_calls"] == 8
    assert result["total_input_tokens"] == 400
    assert result["total_output_tokens"] == 80
    assert result["estimated_cost_usd"] == 0.75
    assert result["priced_trials"] == 2
    assert result["usage_trials"] == 4


def test_external_usage_and_missing_prices_are_not_zero():
    external = trial(provider="external-mcp", usage={"available": False, "calls": None,
                     "input_tokens": None, "output_tokens": None, "estimated_cost_usd": None})
    result = summarize([external])[0]
    assert result["total_model_calls"] is None
    assert result["estimated_cost_usd"] is None
    assert result["usage_trials"] == 0
    assert result["priced_trials"] == 0
    free = trial()
    free["usage"]["estimated_cost_usd"] = 0
    assert summarize([free])[0]["estimated_cost_usd"] == 0
    assert summarize([trial()])[0]["estimated_cost_usd"] is None


def test_summary_preserves_experiment_model_and_provider_boundaries():
    rows = [trial(), trial(group="different"), trial(model="model-b"), trial(provider="other")]
    results = summarize(rows)
    assert len(results) == 4
    assert all(item["trials"] == 1 for item in results)


def test_unfinished_and_interrupted_trials_have_no_gameplay_averages():
    rows = [trial(state="running", stop_reason=None), trial(stop_reason="interrupted")]
    before = deepcopy(rows)
    result = summarize(rows)[0]
    for key in ("success_rate", "mean_score", "median_completion_wall_seconds", "median_wall_seconds",
                "median_emulated_seconds", "median_actions"):
        assert result[key] is None
    assert rows == before


def test_cli_and_dashboard_export_identical_finished_report(session, tmp_path):
    session.wait("one", 2)
    session.finish("action_budget")
    expected = comparison_report(tmp_path)
    args = parser().parse_args(["report", "--runs", str(tmp_path)])
    assert execute(args) == expected
    client = TestClient(create_app(tmp_path))
    assert client.get("/api/report").json() == expected
    assert client.post("/api/report").status_code == 405
    assert expected["summary"][0]["trials"] == 1
    assert "evidence" not in expected["runs"][0]


def test_incomplete_usage_is_visible_even_when_some_tokens_are_known():
    row = trial()
    row["usage"]["accounting_complete"] = False
    assert summarize([row])[0]["incomplete_usage_trials"] == 1
