"""Portable configuration, hashes, and atomic artifact writes."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
from importlib.metadata import distribution
import json
import math
from pathlib import Path

FPS = 4_194_304 / 70_224
BUTTONS = ("up", "down", "left", "right", "a", "b", "start", "select")


def core_provenance():
    """Record the installed core, including local edits and package-manager origin."""
    import pokesim_core

    installed = distribution("pokesim-core")
    direct_url = installed.read_text("direct_url.json")
    root = Path(pokesim_core.__file__).parent
    sources = {str(path.relative_to(root)): digest(path.read_bytes()) for path in sorted(root.rglob("*.py"))}
    return {"version": installed.version, "direct_url": json.loads(direct_url) if direct_url else None,
            "source_sha256": digest(encoded(sources))}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encoded(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def write_json(path: Path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")
    temporary.replace(path)


@dataclass(frozen=True)
class Limits:
    max_frames: int = 2_000_000
    max_actions: int = 20_000
    max_model_calls: int = 10_000
    max_total_tokens: int = 100_000
    max_wall_seconds: float = 21_600
    max_action_frames: int = 120
    max_dialogue_frames: int = 7200
    max_note_bytes: int = 8192
    max_actions_per_decision: int = 8
    max_stagnant_decisions: int = 12
    max_area_tokens: int = 0
    max_loop_tokens: int = 0

    def __post_init__(self):
        for key, value in asdict(self).items():
            if key in ("max_area_tokens", "max_loop_tokens") and type(value) is int and value == 0:
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"{key} must be positive and finite")
            if key != "max_wall_seconds" and type(value) is not int:
                raise ValueError(f"{key} must be an integer")
        if self.max_actions_per_decision > 8:
            raise ValueError("A decision may contain at most eight controller actions")
        if self.max_action_frames > 600:
            raise ValueError("Actions may advance at most 600 frames")


def action(button, hold_frames, release_frames, maximum):
    if button is not None and button not in BUTTONS:
        raise ValueError("Unknown controller button")
    if type(hold_frames) is not int or type(release_frames) is not int:
        raise ValueError("Frame counts must be integers")
    if hold_frames < 1 or release_frames < 0 or hold_frames + release_frames > maximum:
        raise ValueError(f"An action must advance between 1 and {maximum} frames")
    return {"button": button, "hold_frames": hold_frames, "release_frames": release_frames}
