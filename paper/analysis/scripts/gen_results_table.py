"""Generate audited development results and task tables."""
import json
from pathlib import Path

from _assets import record


def write_table(root, name, headers, rows, inputs, description):
    cells = headers + [cell for row in rows for cell in row]
    inset = "3pt" if name in ("catalog", "models") else "6pt"
    body = "#table(columns: " + str(len(headers)) + ", inset: " + inset + ", align: left, "
    body += ", ".join(json.dumps(str(cell), ensure_ascii=False) for cell in cells) + ")\n"
    path = "si/" + name + ".typ"
    (root / path).write_text(body)
    record("tbl." + name, path, kind="table", inputs=inputs, desc=description)


def main():
    root = Path(__file__).resolve().parents[2]
    source = "analysis/inputs/pokebench-development.json"
    data = json.loads((root / source).read_text())
    rows = []
    for model in sorted({row["model"] for row in data["pilot"]}):
        trials = [row for row in data["pilot"] if row["model"] == model]
        rows.append([model, str(sum(row["passed"] for row in trials)) + "/" + str(len(trials)),
                     format(sum(row["tokens"] for row in trials), ","), "All verified"])
    write_table(root, "pilot", ["Model identifier", "Passed", "Reported tokens", "Replay and delivery"],
                rows, [source], "Single-start development pilot, not release results")
    protocol_source = "analysis/inputs/pokebench-v1-protocol.json"
    protocol = json.loads((root / protocol_source).read_text())
    rows = [[row["provider"], row["model"], row["effective_effort"] or "Not adjustable"] for row in protocol["models"]]
    write_table(root, "models", ["Provider", "Registered model identifier", "Effective effort"],
                rows, [protocol_source], "Registered prospective release models, not completed result coverage")
    calibration_source = "analysis/inputs/decision-suite-v044-development.json"
    calibration = json.loads((root / calibration_source).read_text())
    rows = [[row["name"], str(row["reference_wins"]) + "/" + str(row["reference_trials"]),
             str(row["baseline_wins"]) + "/" + str(row["baseline_trials"])] for row in calibration["tasks"]]
    write_table(root, "calibration", ["Experimental task", "Reference", "Simple baseline"], rows,
                [calibration_source], "First fixed-policy development sweep, not held-out performance")
    rows = [[row["name"], row["category"], "Scored" if row["included_in_score"] else "Experimental"]
            for row in data["tasks"]]
    write_table(root, "catalog", ["Task", "Category", "Development status"], rows,
                [source], "Current task inventory with historical scoring status")


if __name__ == "__main__":
    main()
