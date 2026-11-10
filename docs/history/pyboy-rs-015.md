# PyBoy RS 0.1.5 and verified build pairs

November 2026. The emulator dependency moves from PyBoy RS 0.1.1 to 0.1.5. The save state format is still `pyboy-format-15`.

## What changed in the emulator

- 0.1.2 fixes the MBC3 real-time clock. Pokemon Red has no clock, and Gen 1 save states stay byte identical.
- 0.1.3 and 0.1.4 stop a DIV write with sound off from resetting the sound sequencer, which could make a later load fail with "Invalid scheduler state".
- 0.1.5 resets the window line counter at line 0 of every rendered frame. Format 15 states do not store that counter. Under 0.1.1, the first frame after a load in a fresh process drew the window one line low. The frame now matches the run that saved the state.

## The gate

Every run and fixture records the exact emulator build, including the hashes of the native library and the Python binding. The exact rule alone would refuse all 3,628 artifacts recorded under 0.1.1 and all 66 current fixtures.

Replay and fixture loading now also accept a recorded build under a different runtime build when `VERIFIED_EMULATOR_PAIRS` in `src/pokeagent_bench/core.py` lists that exact pair. The table is seeded with one pair, the Linux x86_64 builds of 0.1.1 (recorded) and 0.1.5 (runtime), and it points at this note. A shared state format is not enough, because a release can keep the format and still change behaviour. Any pair not in the table is refused, and the error says how to verify it.

Resuming a paused run keeps the exact build rule, so a run paused under 0.1.1 resumes only under 0.1.1. The legacy PyBoy 2.7.0 rule is unchanged. No artifact was retagged or recorded again.

To add a pair, install the new build, replay the recorded runs with `scripts/verify_emulator_pair.py --rom red.gb <run directories>`, and add the pair only if every run is identical. Record the sweep in a note under `docs/history` and point the entry at it.

## Replay sweep

All 381 Short leaderboard runs (focused-pass-v056, main-v066-astra and main-v067-fable) and two Long runs, long-v073-haiku (100,234 frames, score 10) and long-v069-luna (167,500 frames), were replayed under 0.1.5 with the gate relaxed to the same backend and state format.

- 383 of 383 replay identically. Every action's frame count, screenshot hash, evidence and awards match, and so do the final score, the action hash chain and the trace head.
- 354 runs pass every replay check, 6,668,068 frames in total.
- The other 29 runs are refused before the emulator check with "The catalog specification changed since this run started", and they are refused the same way under 0.1.1. With only that check skipped, all 29 replay identically under 0.1.1 and 0.1.5 (643,205 frames under each).

The 29 are focused-pass-v056 cells 0007 to 0012, 0241 to 0246 (preparation), 0271 to 0276, 0283 to 0285 and 0286 to 0288, and original-navigation-v056 cells 0001, 0004, 0010, 0025 and 0034. Their catalog drift is an existing issue. It is not caused by this change and is not fixed here.

The other 14 Long runs are being replayed under the merged gate. Their result will be added here.

## First frame after a load

Each of the 66 current fixtures (main-v067-fable/fixtures and catalog-v057-navigation) was loaded in a fresh process under both builds and run for 60 frames with no input.

- Frame 1 differs in 20 battle and window scenes: the battle tasks, variant-b, variant-c, objectives-constrained-valuable-capture, operations-battle-switch, the preparation tasks, agatha, bruno and lorelei.
- Frame 2, frame 60 and work RAM at frame 60 are identical in all 66.
- Loading the same fixture twice in one process gives the same frames in all 66 under both builds.

0.1.5 is the correct one. Frame 1 matches the fixture's stored preview in 62 of 66 under 0.1.5 against 43 of 66 under 0.1.1. The other four (battle-league-balanced, objectives-parcel-roundtrip, objectives-quest-trainer and lorelei) match neither build.

New runs from these fixtures can therefore show a different first screen in those 20 scenes, the one that matches the preview. Recorded runs are unaffected, as the sweep shows.

## Checks

- Repository tests under 0.1.5: 842 passed and 9 skipped, and Ruff passes. The new gate tests cover listed, unlisted and legacy builds in replay, fixture loading and resume, and check that every table entry cites an existing note.
- All five wheel hashes in `pyproject.toml` and `uv.lock` match the release's SHA256SUMS.
