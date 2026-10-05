"""Offline review from recorded images and decisions, without running an emulator."""

from __future__ import annotations

import base64
from collections import Counter
from io import BytesIO
import json
import math
from pathlib import Path

from PIL import Image

from .core import FPS, digest
from .review_page import PAGE

MAP_NAMES = {0: "Pallet Town", 37: "Home, ground floor", 38: "Bedroom", 40: "Oak's laboratory", 54: "Pewter Gym"}


def read_artifact(root, name):
    path = root / name
    if Path(name).is_absolute() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("Review artifact must stay inside its run")
    if any(part.is_symlink() for part in (path, *path.parents) if part != root.parent):
        raise ValueError("Review artifacts cannot be symbolic links")
    return path.read_bytes()


def rows(root, name):
    return [json.loads(line) for line in read_artifact(root, name).decode().splitlines() if line.strip()]


def sample_indices(values, count):
    if count <= 0:
        return []
    if len(values) <= count:
        return list(values)
    if count == 1:
        return [values[len(values) // 2]]
    return [values[round(i * (len(values) - 1) / (count - 1))] for i in range(count)]


def highlights(steps, limit=36):
    """Keep endpoints, events, repeat stretches, and evenly spaced context."""
    if len(steps) <= limit:
        return list(range(len(steps)))
    chosen = {0, len(steps) - 1}
    events = [i for i, step in enumerate(steps) if step["events"] and i not in chosen]
    chosen.update(sample_indices(events, limit - len(chosen)))
    repeats = [i for i, step in enumerate(steps) if step["no_new_view_streak"] == 4 and i not in chosen]
    chosen.update(sample_indices(repeats, limit - len(chosen)))
    remaining = [i for i in range(len(steps)) if i not in chosen]
    chosen.update(sample_indices(remaining, limit - len(chosen)))
    return sorted(chosen)


def build_run(root: Path):
    root = root.resolve()
    manifest = json.loads(read_artifact(root, "manifest.json"))
    result = json.loads(read_artifact(root, "result.json"))
    if result["state"] not in ("finished", "paused"):
        raise ValueError("Export a finished or paused run so the review is a consistent snapshot")
    decisions = rows(root, "decisions.jsonl")
    actions = rows(root, "actions.jsonl")
    if not decisions:
        raise ValueError("This run has no recorded model decisions")
    by_frame = {}
    images = {}
    source_hashes = {}

    def save_image(frame, image, source_hash):
        image = image.convert("RGB")
        key = digest(image.tobytes() + str(image.size).encode())
        if frame in by_frame and by_frame[frame] != key:
            raise ValueError("Conflicting game pixels for the same frame")
        by_frame[frame] = key
        source_hashes[frame] = source_hash
        if key not in images:
            stream = BytesIO()
            image.save(stream, format="PNG")
            images[key] = "data:image/png;base64," + base64.b64encode(stream.getvalue()).decode()

    expected = {action["frame"]: action["screenshot_sha256"] for action in actions}
    preview_hash = manifest.get("scenario", {}).get("preview_sha256")
    if preview_hash:
        expected[0] = preview_hash
    views = [decision.get("provider", {}).get(key) for decision in decisions
             for key in ("presentation", "requested_history_presentation")
             if key == "presentation" or decision.get("provider", {}).get(key)]
    for view in views:
        legacy = view and view.get("layout") == "chronological-left-to-right-then-next-row" and view.get("scale") == 3
        compact = view and view.get("layout") == "unique-panels-with-chronological-references-v1" and view.get("scale") == 2
        if not (legacy or compact):
            raise ValueError("Review requires recorded visual-feedback strips")
        raw = read_artifact(root, view["artifact"])
        if digest(raw) != view["image_sha256"]:
            raise ValueError("Model-input image checksum mismatch")
        screens = view["screens"]
        count = view["panel_count"] if compact else len(screens)
        if not 1 <= count <= 33:
            raise ValueError("Invalid image panel count")
        columns = min(3, count)
        scale, header = (2, 32) if compact else (3, 40)
        width, height = 160 * scale, 144 * scale + header
        with Image.open(BytesIO(raw)) as strip:
            if strip.size != (columns * width, math.ceil(count / columns) * height):
                raise ValueError("Unexpected recorded image layout")
            for index, screen in enumerate(screens):
                frame = screen["frame"]
                if frame in expected and expected[frame] != screen["screenshot_sha256"]:
                    raise ValueError("Source-screen checksum does not match controller evidence")
                panel_index = screen["panel"] - 1 if compact else index
                if type(panel_index) is not int or not 0 <= panel_index < count:
                    raise ValueError("Invalid screen panel reference")
                x, y = panel_index % columns * width, panel_index // columns * height + header
                crop = strip.crop((x, y, x + width, y + 144 * scale)).resize((160, 144), Image.Resampling.NEAREST)
                save_image(frame, crop, screen["screenshot_sha256"])
    if actions:
        latest = read_artifact(root, "latest.png")
        if digest(latest) != actions[-1]["screenshot_sha256"]:
            raise ValueError("Final screenshot checksum mismatch")
        with Image.open(BytesIO(latest)) as image:
            save_image(actions[-1]["frame"], image, digest(latest))
    action_groups = {}
    for action in actions:
        parts = action.get("operation_id", "").split("-")
        if len(parts) != 3 or parts[0] != "decision" or not parts[1].isdigit():
            raise ValueError("Controller actions lack decision identifiers")
        action_groups.setdefault(int(parts[1]), []).append(action)
    visits = Counter()
    previous_map = None
    previous_scene = None
    no_new_view = 0
    tokens = 0
    steps = []
    notebook = {}
    for decision in decisions:
        index = decision["index"]
        applied = action_groups.get(index, [])
        before = decision["frame"]
        after = applied[-1]["frame"] if applied else before
        if before not in by_frame or after not in by_frame:
            raise ValueError("Missing screen evidence for a decision boundary")
        if not steps:
            visits[by_frame[before]] += 1
        repeated = visits[by_frame[after]]
        no_new_view = no_new_view + 1 if repeated else 0
        visits[by_frame[after]] += 1
        usage = decision.get("usage", {})
        used = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
        tokens += used
        output = decision.get("decision", {})
        notes = output.get("notes")
        if notes is None:
            notes = notebook
        if isinstance(notes, str):
            try:
                notes = json.loads(notes)
            except ValueError:
                notes = {"observed": [notes]}
        notes = notes if isinstance(notes, dict) else {}
        notebook = notes
        assessment = decision.get("provider", {}).get("assessment", {})
        scene = assessment.get("scene", {})
        scene = scene if isinstance(scene, dict) else {}
        events = []
        maintenance = decision.get("provider", {}).get("maintenance")
        if maintenance:
            events.append({"kind": "agent", "label": "Context summary" if maintenance == "compaction" else "Screenshot recall", "frame": before})
        for action in applied:
            map_id = action.get("evidence", {}).get("map_id")
            if map_id is not None:
                if previous_map is not None and map_id != previous_map:
                    events.append(
                        {"kind": "location", "label": MAP_NAMES.get(map_id, f"Map {map_id}"), "frame": action["frame"]}
                    )
                previous_map = map_id
            for award in action.get("achievements", []):
                events.append(
                    {"kind": "score", "label": str(award.get("id", "Recorded achievement")), "frame": action["frame"]}
                )
        scene_name = scene.get("scene")
        if scene_name in ("dialogue", "menu", "battle") and scene_name != previous_scene:
            events.append({"kind": "agent", "label": "Agent reports " + scene_name, "frame": before})
        previous_scene = scene_name
        steps.append(
            {
                "decision": index,
                "before_frame": before,
                "after_frame": after,
                "before": by_frame[before],
                "after": by_frame[after],
                "source_before_sha256": source_hashes[before],
                "source_after_sha256": source_hashes[after],
                "plan": assessment.get("plan_intent") or notes.get("next_experiment") or (notes.get("observed", [""])[0] if manifest.get("track") == "gameplay" and notes.get("observed") else None) or ("Context summary" if maintenance == "compaction" else "Screenshot recall" if maintenance else "No stated plan recorded"),
                "expected": assessment.get("expected_visible_change", ""),
                "observed": notes.get("observed", []),
                "hypotheses": notes.get("hypotheses", []),
                "unsuccessful_attempts": notes.get("unsuccessful_attempts", []),
                "scene": scene_name,
                "gameplay_input": decision.get("provider", {}).get("context", {}).get("game"),
                "requested_commands": output.get("actions", []),
                "actions": [a["action"] for a in applied],
                "action_frames": [a["executed_frames"] for a in applied],
                "tokens": used,
                "cumulative_tokens": tokens,
                "model_seconds": round(decision.get("seconds", 0), 3),
                "game_seconds": round(after / FPS, 2),
                "unchanged": by_frame[before] == by_frame[after],
                "seen_before": repeated,
                "no_new_view_streak": no_new_view,
                "location": MAP_NAMES.get(previous_map, f"Map {previous_map}")
                if previous_map is not None
                else "Unavailable",
                "events": events,
            }
        )
    last_evidence = actions[-1].get("evidence", {}) if actions else {}
    facts = last_evidence.get("challenge", {})
    return {
        "id": root.name,
        "model": manifest.get("agent", {}).get("model", "Unknown"),
        "task_label": {"starter": "Starter", "badge:boulder": "Brock"}.get(
            manifest.get("scenario", {}).get("objective", {}).get("target"), manifest.get("goal", "Run")),
        "objective": manifest.get("scenario", {}).get("objective", {}).get("description", manifest.get("goal")),
        "benchmark": manifest.get("benchmark"),
        "track": manifest.get("track"),
        "completed": result.get("completed"),
        "stop_reason": result.get("stop_reason"),
        "score": result.get("score"),
        "score_max": result.get("score_max"),
        "tokens": result.get("usage", {}).get("input_tokens", 0) + result.get("usage", {}).get("output_tokens", 0),
        "accounting_complete": result.get("usage", {}).get("accounting_complete"),
        "wall_seconds": result.get("wall_seconds"),
        "frames": result.get("frames"),
        "actions": result.get("actions"),
        "trace_head": result.get("trace_head"),
        "final_evaluator": {
            "valid": last_evidence.get("valid"),
            "starter_flag": last_evidence.get("story", {}).get("starter"),
            "party_count": facts.get("party_count"),
            "party_species_ids": facts.get("party_species"),
        },
        "steps": steps,
        "highlights": highlights(steps),
        "images": images,
    }


def review_html(runs, seconds=None):
    if seconds is not None and (type(seconds) is not int or not 15 <= seconds <= 600):
        raise ValueError("Review duration must be 15 to 600 seconds per run")
    if not runs:
        raise ValueError("Select at least one run")
    payload = {"format": 1, "seconds": seconds, "runs": [build_run(Path(run)) for run in runs]}
    data = (
        json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
        .replace("<", r"\u003c")
        .replace(">", r"\u003e")
        .replace("&", r"\u0026")
    )
    return PAGE.replace("__REVIEW_DATA__", data)


def export_review(runs, output: Path, seconds=None):
    if output.exists():
        raise ValueError("Review output already exists, choose a new filename")
    page = review_html(runs, seconds)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as stream:
        stream.write(page)
    return {
        "output": str(output.resolve()),
        "runs": len(runs),
        "recap_seconds_per_run": seconds,
        "bytes": output.stat().st_size,
    }
