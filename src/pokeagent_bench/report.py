"""Read finished and live runs without granting access to evaluator artifacts."""
import json
from datetime import datetime, timezone
from pathlib import Path
import statistics

from .core import digest, encoded


def read_runs(root: Path):
    rows = []
    if not root.exists():
        return rows
    for directory in sorted(root.iterdir()):
        if directory.is_symlink() or not directory.is_dir():
            continue
        try:
            manifest = json.loads((directory / "manifest.json").read_text())
            result = json.loads((directory / "result.json").read_text())
            config = {key: manifest[key] for key in ("benchmark", "track", "goal", "limits", "labels_sha256")}
            config["observation_policy"] = manifest.get("observation_policy")
            config["catalog_sha256"] = manifest.get("catalog_sha256")
            config["journal"] = manifest.get("journal", False)
            config["recovery_protocol"] = manifest.get("recovery_protocol")
            config["scenario"] = manifest["scenario"]
            config["source_sha256"] = manifest.get("source_sha256")
            config["core"] = manifest.get("core")
            agent = manifest["agent"]
            config["prompt"] = agent.get("prompt_sha256")
            config["reasoning_effort"] = agent.get("reasoning_effort")
            config["cli_version"] = agent.get("cli_version")
            config["harness"] = agent.get("harness")
            config["configuration"] = agent.get("configuration")
            config["memory"] = agent.get("memory")
            config["max_output_tokens"] = agent.get("max_output_tokens")
            config["runner"] = "external" if agent.get("provider") == "external-mcp" else "controlled"
            if result["state"] == "running" and result.get("updated_at"):
                updated = datetime.fromisoformat(result["updated_at"])
                result["wall_seconds"] += max(0, (datetime.now(timezone.utc) - updated).total_seconds())
            rows.append({"id": directory.name, "group": digest(encoded(config))[:12],
                         "provider": agent.get("provider"), "model": agent.get("model"),
                         "benchmark": manifest["benchmark"], **result})
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return sorted(rows, key=lambda row: (row["group"], -row["score"], row["wall_seconds"]))


def summarize(rows):
    groups = {}
    for row in rows:
        key = (row["group"], row["provider"], row["model"])
        groups.setdefault(key, []).append(row)
    output = []
    for (group, provider, model), trials in groups.items():
        finished = [row for row in trials if row["state"] == "finished"]
        errors = [row for row in finished if row["stop_reason"] in ("provider_error", "infrastructure_error", "interrupted", "usage_unavailable")]
        evaluated = [row for row in finished if row not in errors]
        completed = [row for row in evaluated if row["completed"]]
        usage = [row["usage"] for row in trials if row.get("usage", {}).get("available", False)]
        priced = [item["estimated_cost_usd"] for item in usage if item.get("estimated_cost_usd") is not None]
        output.append({"group": group, "provider": provider, "model": model,
                       "trials": len(trials), "running": sum(row["state"] == "running" for row in trials),
                       "paused": sum(row["state"] == "paused" for row in trials),
                       "evaluated": len(evaluated), "errors_or_interruptions": len(errors),
                       "completed": len(completed),
                       "success_rate": len(completed) / len(evaluated) if evaluated else None,
                       "mean_score": statistics.mean(row["score"] for row in evaluated) if evaluated else None,
                       "median_completion_wall_seconds": statistics.median(row["wall_seconds"] for row in completed)
                       if completed else None,
                       "median_wall_seconds": statistics.median(row["wall_seconds"] for row in evaluated)
                       if evaluated else None,
                       "median_emulated_seconds": statistics.median(row["emulated_seconds"] for row in evaluated)
                       if evaluated else None,
                       "median_actions": statistics.median(row["actions"] for row in evaluated)
                       if evaluated else None,
                       "incomplete_usage_trials": sum(item.get("accounting_complete") is False for item in usage),
                       "usage_trials": len(usage), "priced_trials": len(priced),
                       "total_model_calls": sum(item["calls"] for item in usage) if usage else None,
                       "total_input_tokens": sum(item["input_tokens"] for item in usage) if usage else None,
                       "total_output_tokens": sum(item["output_tokens"] for item in usage) if usage else None,
                       "estimated_cost_usd": sum(priced) if priced else None})
    return output


def comparison_report(root: Path):
    """Build aggregates and individual trials from the same artifact snapshot."""
    rows = read_runs(root)
    return {"runs": rows, "summary": summarize(rows)}
