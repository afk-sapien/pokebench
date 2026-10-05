"""Screen-only feedback, with no inferred geometry or automatic emulator ticks."""
from __future__ import annotations

import base64
from collections import Counter, deque
from io import BytesIO
import json
import math
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

from .core import digest

MEMORY_FIELDS = ("observed", "hypotheses", "unsuccessful_attempts", "next_experiment")
NOTE_SCHEMA = {
    "anyOf": [{"type": "null"}, {"type": "object", "additionalProperties": False,
        "properties": {key: ({"type": "string"} if key == "next_experiment" else
                            {"type": "array", "items": {"type": "string"}}) for key in MEMORY_FIELDS},
        "required": list(MEMORY_FIELDS)}]
}


def normalize_notes(notes):
    if notes is None:
        return None
    if not isinstance(notes, dict) or set(notes) != set(MEMORY_FIELDS):
        raise ValueError("Notebook needs observed, hypotheses, unsuccessful_attempts, next_experiment")
    for key, value in notes.items():
        if key == "next_experiment":
            if not isinstance(value, str):
                raise ValueError("Next experiment must be text")
        elif not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ValueError("Notebook evidence fields must be lists of text")
    return json.dumps(notes, sort_keys=True, ensure_ascii=False)


def public_context(observation):
    status = observation["status"]
    result = {"frame": observation["frame"], "objective": status.get("objective"),
              "goal": status["goal"], "track": status["track"],
              "emulated_seconds": status["emulated_seconds"],
              "remaining": status["remaining"], "token_budget": status["token_budget"],
              "max_action_frames": status["max_action_frames"],
              "max_actions_per_decision": status["max_actions_per_decision"],
              "max_note_bytes": status["max_note_bytes"]}
    if status["track"] in ("structured", "gameplay"):
        result["game"] = observation["game"]
    if status["track"] == "gameplay":
        result["max_dialogue_frames"] = status["max_dialogue_frames"]
    return result


def pixels(png):
    with Image.open(BytesIO(png)) as image:
        return image.convert("RGB")


def change(before, after):
    left, right = pixels(before), pixels(after)
    if left.size != right.size:
        raise ValueError("Game screenshot dimensions changed")
    diff = ImageChops.difference(left, right)
    red, green, blue = diff.split()
    histogram = ImageChops.lighter(ImageChops.lighter(red, green), blue).histogram()
    count = left.width * left.height - histogram[0]
    return {"image_changed": count > 0,
            "changed_pixel_fraction": round(count / (left.width * left.height), 6)}


def pack_screens(samples, *, compact=False):
    """Losslessly enlarge game pixels and optionally reuse identical panels."""
    scale, header = (2, 32) if compact else (3, 40)
    width, height = pixels(samples[0]["png"]).size
    unique = []
    indices = {}
    entries = []
    for sample in samples:
        image = pixels(sample["png"])
        if image.size != (width, height):
            raise ValueError("Game screenshot dimensions changed")
        key = digest(image.tobytes())
        if not compact or key not in indices:
            indices[key] = len(unique)
            unique.append(sample)
        entry = {key: value for key, value in sample.items() if key != "png"}
        entry["screenshot_sha256"] = digest(sample["png"])
        if compact:
            entry["panel"] = indices[key] + 1
        entries.append(entry)
    if compact:
        current_index = entries[-1]["panel"] - 1
        order = [i for i in range(len(unique)) if i != current_index] + [current_index]
        remap = {old + 1: new + 1 for new, old in enumerate(order)}
        unique = [unique[i] for i in order]
        for entry in entries:
            entry["panel"] = remap[entry["panel"]]
    columns = min(3, len(unique))
    cell_width, cell_height = width * scale, height * scale + header
    panel = Image.new("RGB", (columns * cell_width, math.ceil(len(unique) / columns) * cell_height), "white")
    draw = ImageDraw.Draw(panel)
    for number, sample in enumerate(unique):
        x, y = number % columns * cell_width, number // columns * cell_height
        if compact:
            is_current = number == len(unique) - 1
            label = f"CURRENT | panel {number + 1}" if is_current else f"EARLIER | panel {number + 1}"
            label_frame = samples[-1]["frame"] if is_current else sample["frame"]
        else:
            label = "BEFORE" if number == 0 and len(samples) > 1 else "CURRENT" if len(samples) == 1 else f"AFTER {number}"
        if compact:
            draw.text((x + 8, y + 3), label, fill="black")
            draw.text((x + 8, y + 17), f"frame {label_frame}", fill="black")
        else:
            draw.text((x + 8, y + 3), f"{label} | frame {sample['frame']}", fill="black")
        if not compact and "feedback" in sample:
            action = sample["feedback"]["action"]
            draw.text((x + 8, y + 19),
                      f"{action['button'] or 'wait'}: hold {action['hold_frames']}, release {action['release_frames']}", fill="black")
        panel.paste(pixels(sample["png"]).resize((width * scale, height * scale), Image.Resampling.NEAREST), (x, y + header))
    stream = BytesIO()
    panel.save(stream, format="PNG")
    layout = {"scale": scale, "layout": "chronological-left-to-right-then-next-row"}
    if compact:
        layout.update(layout="unique-panels-with-chronological-references-v1", panel_count=len(unique), header_height=header, current_panel=len(unique))
    return stream.getvalue(), entries, layout


class VisualFeedback:
    """Keep the previous decision's screen and every ensuing controller result."""

    def __init__(self, output: Path, *, with_motion=False, compact=False, current_only=False):
        self.output = output
        self.current_only = current_only
        self.with_motion = with_motion
        self.compact = compact
        self.samples = []
        self.visits = Counter()
        self.unchanged = {}
        self.recent_views = deque(maxlen=16)

    def prepare(self, observation, index):
        current = base64.b64decode(observation["screenshot"]["base64"], validate=True)
        if not self.samples:
            self.samples.append({"frame": observation["frame"], "png": current})
            self.visits[digest(current)] += 1
            self.recent_views.append(digest(current))
        if self.samples[-1]["frame"] != observation["frame"] or self.samples[-1]["png"] != current:
            raise ValueError("Visual history does not match current observation")
        png, entries, layout = pack_screens(self.samples[-1:] if self.current_only else self.samples, compact=self.compact)
        directory = self.output / "observations"
        directory.mkdir(exist_ok=True)
        filename = f"{index:06d}.png"
        (directory / filename).write_bytes(png)
        view = {"base64": base64.b64encode(png).decode(), "image_sha256": digest(png),
                "artifact": f"observations/{filename}", **layout, "screens": entries,
                "screen_history": {"current_image_occurrences": self.visits[digest(current)],
                    "unique_images_seen": len(self.visits),
                    "recent_sample_count": len(self.recent_views),
                    "recent_unique_images": len(set(self.recent_views)),
                    "unchanged_inputs_from_this_exact_image": [
                        {"button": key[0] or "wait", "hold_frames": key[1], "release_frames": key[2], "count": count}
                        for key, count in self.unchanged.get(digest(current), Counter()).most_common(8)]}}
        self.samples = [{"frame": observation["frame"], "png": current}]
        return view

    def record(self, command, before_frame, after_frame, screenshot):
        png = base64.b64decode(screenshot["base64"], validate=True)
        previous = self.samples[-1]
        if previous["frame"] != before_frame:
            raise ValueError("Missing controller observation")
        feedback = {"action": command, "before_frame": before_frame, "frame": after_frame,
                    "executed_frames": after_frame - before_frame, **change(previous["png"], png)}
        if self.with_motion:
            from .screen_motion import estimate_screen_translation
            feedback["screen_translation_estimate"] = estimate_screen_translation(previous["png"], png)
        fingerprint = digest(png)
        self.visits[fingerprint] += 1
        self.recent_views.append(fingerprint)
        if not feedback["image_changed"]:
            counter = self.unchanged.setdefault(fingerprint, Counter())
            counter[(command["button"], command["hold_frames"], command["release_frames"])] += 1
        self.samples.append({"frame": after_frame, "png": png, "feedback": feedback})
        return feedback
