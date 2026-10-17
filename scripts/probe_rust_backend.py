"""Unscored, isolated Gen1 emulator parity probe using identical saved bytes.

Run with --legacy-python and --rust-python pointing to separate environments.
This explicitly tests legacy state import. It never migrates registered saves,
changes the default dependency, starts model calls, or writes game state files.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess


INPUTS = [(None, 1), ("right", 8), (None, 8), ("a", 8), (None, 8),
          ("b", 8), (None, 8), ("down", 8), (None, 8)]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def worker(rom, scenario):
    from importlib.metadata import version
    from pokesim_core.emulator import GameBoy
    from pokesim_core.gen1 import read_bag, read_party, read_progress
    try:
        from pokesim_core.emulator_state import runtime_provenance
        runtime = runtime_provenance()
    except ModuleNotFoundError as error:
        if error.name != "pokesim_core.emulator_state":
            raise
        runtime = {"backend": "pyboy", "version": version("pyboy")}
    manifest = json.loads((scenario / "scenario.json").read_text())
    state = (scenario / "initial.state").read_bytes()
    if manifest.get("game") != "red" or manifest.get("format") != 1:
        raise ValueError("Only registered Gen1 Red starts are supported")
    if manifest.get("pyboy_version") != "2.7.0":
        raise ValueError("Probe requires an explicit PyBoy 2.7.0 source")
    if manifest["state_sha256"] != digest(state) or manifest["rom_sha256"] != digest(rom.read_bytes()):
        raise ValueError("Scenario state or ROM checksum mismatch")
    rows = []
    with GameBoy(rom, state, allowed_games=("red",)) as engine:
        for button, frames in INPUTS:
            if button:
                engine.press(button)
            engine.tick(frames, render=True)
            if button:
                engine.release(button)
            facts = {"party": read_party(engine.memory), "bag": read_bag(engine.memory),
                     "progress": read_progress(engine.memory)}
            rows.append({"wram_sha256": digest(bytes(engine.memory[0xc000:0xe000])),
                         "screen_sha256": digest(engine.screenshot()),
                         "facts_sha256": digest(json.dumps(facts, sort_keys=True).encode())})
    return {"runtime": runtime, "core_version": version("pokesim-core"),
            "source_state_sha256": digest(state), "steps": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, type=Path)
    parser.add_argument("--scenario", required=True, type=Path)
    parser.add_argument("--legacy-python", type=Path)
    parser.add_argument("--rust-python", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        print(json.dumps(worker(args.rom, args.scenario)))
        return
    if not all((args.legacy_python, args.rust_python, args.output)):
        parser.error("Provide both isolated Python interpreters and --output")
    if args.output.exists():
        raise ValueError("Probe output already exists")
    results = {}
    for label, interpreter in (("legacy", args.legacy_python), ("rust", args.rust_python)):
        completed = subprocess.run([str(interpreter), "-I", str(Path(__file__).resolve()), "--worker",
                                    "--rom", str(args.rom.resolve()), "--scenario", str(args.scenario.resolve())],
                                   check=True, capture_output=True, text=True, timeout=120)
        results[label] = json.loads(completed.stdout)
    if results["legacy"]["runtime"]["backend"] != "pyboy":
        raise ValueError("Legacy interpreter must use the PyBoy backend")
    if results["rust"]["runtime"]["backend"] != "pyboy-rs":
        raise ValueError("Rust interpreter must use the PyBoy RS backend")
    if any(len(result["steps"]) != len(INPUTS) for result in results.values()) or not INPUTS:
        raise ValueError("Probe must return every expected comparison checkpoint")
    comparisons = [{"step": index, **{key: old[key] == new[key] for key in old}}
                   for index, (old, new) in enumerate(zip(results["legacy"]["steps"], results["rust"]["steps"], strict=True))]
    report = {"format": 1, "scored": False,
              "scope": "Bounded input smoke test. Passing does not establish full emulator parity",
              "inputs": INPUTS, "results": results,
              "comparisons": comparisons,
              "passed": all(all(value for key, value in row.items() if key != "step") for row in comparisons)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as handle:
        handle.write(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"passed": report["passed"], "output": str(args.output)}))


if __name__ == "__main__":
    main()
