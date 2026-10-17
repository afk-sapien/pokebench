"""Derive the current report numbers from frozen, sanitized inputs."""
import json
from pathlib import Path

from _stats import Stats


def main():
    root = Path(__file__).resolve().parents[2]
    release = json.loads((root / "analysis/inputs/pokebench-development.json").read_text())
    calibration = json.loads((root / "analysis/inputs/tactical-reliability-v042.json").read_text())
    protocol = json.loads((root / "analysis/inputs/pokebench-v1-protocol.json").read_text())
    stats = Stats()
    values = {
        "release.models": len(protocol["models"]),
        "release.tasks": len(protocol["tasks"]),
        "release.variants": protocol["variants"],
        "release.planned": protocol["planned_attempts"],
        "release.budget": protocol["total_token_budget"],
        "release.maximum": protocol["maximum_planned_tokens"],
        "release.turns": protocol["context_turns"],
        "release.context": protocol["compact_at"],
        "release.summaries": protocol["paid_summaries"],
        "release.reserve": protocol["in_flight_reserve"],
        "release.claude_output": protocol["transports"]["claude"]["max_output_tokens"],
        "release.eligible": sum(row["score_eligible"] for row in protocol["tasks"]),
        "catalog.active": len(release["tasks"]),
        "catalog.scored": sum(row["included_in_score"] for row in release["tasks"]),
        "catalog.experimental": sum(not row["included_in_score"] for row in release["tasks"]),
        "catalog.retired": len(release["retired"]),
        "models.historical": len(release["historical_models"]),
        "pilot.attempts": len(release["pilot"]),
        "pilot.tasks": len({row["task"] for row in release["pilot"]}),
        "pilot.models": len({row["model"] for row in release["pilot"]}),
        "pilot.tokens": sum(row["tokens"] for row in release["pilot"]),
    }
    for model, label in (("gpt-6-astra", "astra"), ("gpt-5.6-terra", "terra"), ("gpt-5.6-luna", "luna")):
        rows = [row for row in release["pilot"] if row["model"] == model]
        if not rows:
            raise ValueError("Missing expected pilot model: " + model)
        values["pilot." + label + ".wins"] = sum(row["passed"] for row in rows)
        values["pilot." + label + ".trials"] = len(rows)
    candidate = next(row for row in calibration["candidate_reports"] if row["status"] == "validated")
    values["calibration.starts"] = candidate["attempts_per_policy"]
    for key, value in candidate["wins"].items():
        values["calibration." + key] = value
    focused_source = "analysis/inputs/focused-v060.json"
    focused = json.loads((root / focused_source).read_text())
    values.update({"focused." + key: value for key, value in focused["counts"].items()})
    values.update({"focused." + key: value for key, value in focused["usage"].items()})
    values.update({"focused." + key: focused["audit"][key] for key in
                   ("format_error_decisions", "runs_with_format_errors", "trace_decisions")})
    for setting in ("context_turns", "compact_at"):
        observed = focused["conditions"][setting]
        if len(observed) != 1:
            raise ValueError("Report prose assumes one common gameplay setting: " + setting)
        values["focused." + setting] = int(next(iter(observed)))
    values["focused.budget_stops"] = focused["audit"]["stop_reasons"].get("model_call_budget", 0)
    values["focused.challenge_failures"] = focused["audit"]["stop_reasons"].get("challenge_failed", 0)
    values["focused.warp_errors"] = sum(row["audit"]["format_error_decisions"] for row in focused["cells"]
                                        if row["task_id"] == "navigation-warp-puzzle")
    values["repeat.planned"] = focused["repeats"]["planned"]
    values["repeat.finished"] = focused["repeats"]["finished"]
    values["repeat.tokens"] = focused["repeats"]["reported_tokens"]
    values["repeat.changed"] = sum(row["changed"] for row in focused["repeats"]["rows"])
    values["repeat.pairs"] = len(focused["repeats"]["rows"])
    values["repeat.tasks"] = len({row["task_id"] for row in focused["repeats"]["rows"]})
    for model in focused["models"]:
        stats.add("focused.score." + model["label"].lower(), model["score"] * 100,
                  fmt=".1f", desc="Equal-category overall score for " + model["label"], between=(0, 100))
    for key, value in values.items():
        stats.add(key, value, fmt=",", desc=key.replace(".", " "), between=(0, 2000000000))
    return stats.write(inputs=[focused_source, "analysis/inputs/pokebench-development.json", "analysis/inputs/tactical-reliability-v042.json", "analysis/inputs/pokebench-v1-protocol.json"])


if __name__ == "__main__":
    raise SystemExit(main())
