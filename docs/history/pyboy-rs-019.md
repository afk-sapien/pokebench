# PyBoy RS 0.1.9 and PokeSim Core 0.12.4

November 2026. The emulator dependency moves from PyBoy RS 0.1.7 to 0.1.9 and the core from PokeSim Core 0.12.3 to 0.12.4. The save state format is still `pyboy-format-15`. The task specs, start states, fixture pack, prompts, run limits and scoring are unchanged.

## What changed upstream

- PyBoy RS 0.1.8 runs the core faster with the same save states, screens and audio as 0.1.7. It caches decoded ROM instructions, draws tile rows eight pixels at a time and, with the picture off, skips LCD mode changes nothing observes. Every interrupt still happens at the same cycle.
- PyBoy RS 0.1.9 is 0.1.8 with one fix. A ROM write, such as each hook hit, drops only the cached instructions that read the written byte instead of the whole cache, so a hook no longer slows the core down. The save states, screens and audio are the same as 0.1.8.
- Neither release changes the state format or the Python API. The binding hash is the same as 0.1.7, and only the native library hash changes.
- PokeSim Core 0.12.4 adds a Gen II walking reader, a Gen II `flash` field, a decoded region cache in `pokecore.regions` and four Gen I names. It requires PyBoy RS 0.1.7 or later below 0.2.

The installed Core sources differ in six files and add `regions.py`. In `gen1` and `shortcuts` the changes only add names or move one constant. The one changed function the benchmark calls is `snapshot.read_fields`. It reads the same addresses and returns the same fields. The two Pokédex sets are now shared while their bytes are unchanged, and the party moves to the end of the returned dict. The benchmark reads each field by name, so the order plays no part.

## The gate

`VERIFIED_EMULATOR_PAIRS` in `src/pokeagent_bench/core.py` gains three pairs, and all three point at this note.

1. PyBoy RS 0.1.7 recorded under 0.1.9. Runs made on release 0.37.4 recorded 0.1.7.
2. PyBoy RS 0.1.5 recorded under 0.1.9. The Haiku rerun and 10 of the 58 set-up fixtures recorded 0.1.5.
3. PyBoy RS 0.1.1 recorded under 0.1.9. The published traces and the other 48 set-up fixtures recorded 0.1.1.

All three pairs name the Linux x86_64 builds. The older pairs stay. Resume keeps the exact build rule, so a run paused under 0.1.7 resumes only under 0.1.7. No artifact was retagged or recorded again.

## Replay proof

Every replay below ran `scripts/verify_emulator_pair.py` under 0.1.9 with no check relaxed. A replay passes only when every action's frame count, screenshot hash, evidence and awards match the recorded log, and the final score, action hash chain and trace head match too. Each set ran in one process at nice 10 while other work used most of the machine.

| Recorded under | Runs | Passed | Actions | Frames |
| --- | ---: | ---: | ---: | ---: |
| 0.1.7, three random controller smoke runs | 3 | 3 | 219 | 5,562 |
| 0.1.5, Haiku Short cells 1 to 3 | 3 | 3 | 3,543 | 91,616 |
| 0.1.5, the Haiku Long run | 1 | 1 | 4,192 | 111,864 |
| 0.1.1, main-v067-fable cells 1 to 3 | 3 | 3 | 2,768 | 69,727 |
| Total | 10 | 10 | 10,722 | 278,769 |

The Long run is 111,864 frames, 4,192 actions and a score of 13, the same as under 0.1.5 and 0.1.7.

### Fixtures

Each of the 58 set-up fixtures in the 0.37.4 data was loaded in a fresh process under each install and run for 60 frames with no input, once under PyBoy RS 0.1.7 with Core 0.12.3 and once under 0.1.9 with Core 0.12.4. The screen after frames 1, 2 and 60, the work RAM and the saved state after frame 60 are identical in all 58.

### Not run yet

The full sweep of the 0.1.7 note was not run for this change. That is the other 43 Haiku Short cells, the 16 published Long runs and the 400 published Short runs. It needs the machine for about 80 minutes with six workers.

## Checks

1. The full test suite passes, 1131 passed and 12 skipped. `ruff check .` is clean.
2. All five wheel hashes in `pyproject.toml` match the SHA256SUMS of PyBoy RS v0.1.9, and the Core wheel hash matches pokecore-v0.12.4.

This change edits the top-level harness sources, so the harness source hash differs from the accepted 0.37.4 entry. `pokebench verify` refuses on this checkout until a release adds its own accepted entry.
