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

    focused_source = "analysis/inputs/focused-v060.json"
    focused = json.loads((root / focused_source).read_text())
    rows = [[m["label"], f'{100*m["score"]:.1f}', f'{m["tokens"]/1e6:.2f}',
             str(m["finished"]) + "/" + str(m["planned"])] for m in focused["models"]]
    write_table(root, "focused-ranking", ["Model", "Score (%)", "Tokens (M)", "Finished"],
                rows, [focused_source], "Initial pass scores and selected-attempt token totals")
    rows = []
    for model in focused["models"]:
        rows.append([model["label"]] + [f'{100*model["categories"][c]:.1f}' for c in focused["categories"]])
    write_table(root, "focused-categories", ["Model", "Nav.", "Battle", "Menus", "Prep.", "Quests"],
                rows, [focused_source], "Per-category scores in percent")
    names = {m["model"]: m["label"] for m in focused["models"]}
    sensitivity = {row["model"]: row for row in focused["task_sensitivity"]["rows"]}
    rows = [[m["label"], str(sensitivity[m["model"]]["best_rank"]),
             str(sensitivity[m["model"]]["worst_rank"])] for m in focused["models"]]
    write_table(root, "focused-sensitivity", ["Model", "Best rank", "Worst rank"], rows,
                [focused_source], "Ranks after omitting each task group once, not confidence intervals")
    short_tasks = {"navigation-forest-crossing": "Forest", "battle-underleveled-status-setup": "Lorelei",
                   "preparation-move-replacement-across-fights": "Move prep."}
    rows = []
    for row in focused["repeats"]["rows"]:
        scores = [f'{100*r["value"]:.0f}' if r["state"] == "finished" and r["value"] is not None else r["state"]
                  for r in row["repeats"]]
        rows.append([names[row["model"]], short_tasks[row["task_id"]], f'{100*row["initial"]:.0f}'] + scores)
    write_table(root, "focused-repeats", ["Model", "Task", "Initial (%)", "Repeat 2 (%)", "Repeat 3 (%)"],
                rows, [focused_source], "Post hoc matched repeats, pending attempts explicitly labeled")
    for category in focused["categories"]:
        rows = [[row["title"], str(row["decision_limit"]), f'{row["token_limit"]/1e6:g}']
                for row in focused["tasks"] if row["category"] == category]
        write_table(root, "focused-" + category, ["Task", "Decisions", "Tokens (M)"], rows,
                    [focused_source], "Current " + category + " tasks and actual trial budgets")
    rows = [[m["label"], m["model"]] for m in focused["models"]]
    write_table(root, "focused-identifiers", ["Display name", "Recorded provider identifier"], rows,
                [focused_source], "Provider identifiers recorded in attempt manifests")


if __name__ == "__main__":
    main()
