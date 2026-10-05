"""Freeze public result fields and artifact checksums for manuscript analysis."""
from pathlib import Path

from .core import digest, write_json
from .report import read_runs, summarize


def export_results(root: Path, output: Path):
    rows = read_runs(root)
    finished = [row for row in rows if row["state"] == "finished"]
    allowed = {"id", "group", "provider", "model", "benchmark", "goal", "track", "state", "stop_reason",
               "completed", "score", "score_max", "wall_seconds", "emulated_seconds", "frames", "actions"}
    usage_keys = {"available", "accounting_complete", "calls", "input_tokens", "output_tokens",
                  "model_seconds", "estimated_cost_usd"}
    public = []
    sources = {}
    for row in finished:
        clean = {key: value for key, value in row.items() if key in allowed}
        clean["usage"] = {key: value for key, value in row["usage"].items() if key in usage_keys}
        public.append(clean)
        directory = root / row["id"]
        sources[row["id"]] = {name: digest((directory / name).read_bytes())
                              for name in ("manifest.json", "result.json", "actions.jsonl")
                              if (directory / name).is_file()}
    report = {"schema": 1, "runs": public, "summary": summarize(public), "source_sha256": sources,
              "excluded_running": len(rows) - len(finished),
              "interpretation": "Controller smoke runs do not establish model gameplay performance"}
    output.parent.mkdir(parents=True, exist_ok=True)
    write_json(output, report)
    return {"output": str(output), "finished_trials": len(finished), "sha256": digest(output.read_bytes())}
