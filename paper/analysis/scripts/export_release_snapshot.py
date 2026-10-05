"""Freeze allowlisted development summaries for the paper, without private artifacts."""
import argparse
import hashlib
import json
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pick(row, keys):
    return {key: row[key] for key in keys if key in row}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--combined", type=Path, required=True)
    parser.add_argument("--pilot-audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    combined = json.loads(args.combined.read_text())
    audit = json.loads(args.pilot_audit.read_text())
    rows = audit["tasks"]
    if audit.get("finished_tasks") != len(rows):
        raise ValueError("Pilot completion count does not match the audited rows")
    identities = [(row["model"], row["task"], row["repeat"]) for row in rows]
    if len(set(identities)) != len(identities):
        raise ValueError("Duplicate pilot model-task-repeat identity")
    checks = ("replay_verified", "conversation_order_verified", "input_delivery_verified", "state_updates_verified")
    if not rows or any(not all(row.get(check) is True for check in checks) for row in rows):
        raise ValueError("The development pilot must have complete delivery and replay audits")
    result = {
        "schema_version": 1,
        "evidence_status": "development-only",
        "sources": {"combined_sha256": digest(args.combined), "pilot_audit_sha256": digest(args.pilot_audit)},
        "ranking_version": combined["analysis"],
        "tasks": [pick(row, ("id", "name", "category", "difficulty", "included_in_score")) for row in combined["tasks"]],
        "retired": [pick(row, ("id", "name", "reason")) for row in combined["retired_tasks"]],
        "historical_models": [pick(row, ("model", "score", "scored_tasks", "tokens")) for row in combined["models"]],
        "pilot": [pick(row, ("id", "model", "task", "repeat", "calls", "tokens", "passed", *checks)) for row in rows],
        "notes": ["Historical ranking combines declared development cohorts and is not a frozen release comparison.", "The pilot has one attempt per task and model. It cannot estimate within-task reliability.", "No screenshots, save states, prompts, responses, local paths, or credentials are exported."]
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
