"""Replay recorded runs under the installed emulator to verify a build pair.

For each run, the build recorded in its manifest and the installed runtime
build are accepted as a candidate pair in this process only. Every other
replay check is unchanged. Nothing is written.

Add a pair to VERIFIED_EMULATOR_PAIRS in core.py only when every run in the
sweep replays identically, and record the sweep in a docs/history note.
Prints one JSON line per run and a summary line. Exits 1 if any run fails.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

from pokeagent_bench import core, session


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--list", type=Path, help="file with one run directory per line")
    parser.add_argument("runs", nargs="*", type=Path)
    args = parser.parse_args()
    runs = list(args.runs) + ([Path(line) for line in args.list.read_text().split()] if args.list else [])
    if not runs:
        parser.error("name at least one run directory")
    runtime = core.emulator_provenance()
    print(json.dumps({"runtime": runtime}), flush=True)
    listed = core.VERIFIED_EMULATOR_PAIRS
    failed = 0
    frames = 0
    for run in runs:
        started = time.time()
        recorded = json.loads((run / "manifest.json").read_text()).get("emulator")
        row = {"run": str(run), "recorded": recorded}
        core.VERIFIED_EMULATOR_PAIRS = listed + ({"recorded": recorded, "runtime": runtime, "evidence": "candidate"},)
        try:
            row.update(ok=True, **session.replay(args.rom, run))
            frames += row["frames"]
        except Exception as error:
            row.update(ok=False, error=f"{type(error).__name__}: {error}")
            failed += 1
        finally:
            core.VERIFIED_EMULATOR_PAIRS = listed
        row["seconds"] = round(time.time() - started, 1)
        print(json.dumps(row), flush=True)
    print(json.dumps({"runs": len(runs), "identical": len(runs) - failed, "failed": failed, "frames": frames}),
          flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
