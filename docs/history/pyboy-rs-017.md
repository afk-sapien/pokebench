# PyBoy RS 0.1.7 and PokeSim Core 0.12.3

November 2026. The emulator dependency moves from PyBoy RS 0.1.5 to 0.1.7 and the core from PokeSim Core 0.12.0 to 0.12.3. The save state format is still `pyboy-format-15`. The task specs, start states, fixture pack, prompts, run limits and scoring are unchanged, and so is the harness name `red-v0.63-short-guard`.

## What changed upstream

- PyBoy RS 0.1.6 keeps every clock below about 2^47 cycles, so a very long run keeps saving states that load again. A state at or below 2^48 cycles loads byte for byte as before. Benchmark runs stay far below that.
- PyBoy RS 0.1.7 has the same save states and audio as 0.1.6 and runs faster. It skips screen and audio copies a tick does not need, copies plain memory ranges in one slice and advances the sound channels in closed form. Rendering every frame is unchanged.
- PokeSim Core 0.12.1 adds the Route 22 rival tables to `romdata.layouts`, which only a starter randomizer patch uses. The benchmark never patches the ROM.
- PokeSim Core 0.12.2 and 0.12.3 require PyBoy RS 0.1.6 and 0.1.7. 0.12.3 keeps a decoded value beside the per-step memory copy with `snapshot_memo` and reads box counts from that copy. It removes `snapshot.decoder_backend()` and `POKESIM_CORE_DECODER`. The benchmark uses neither, and neither install has the native decoder, so both decode with the same Python decoder.

The installed Core sources differ in six files. `snapshot.read_fields` reads the same addresses and returns the same fields. The other changes add the memo, the Yellow copy and the starter table, and bump the version.

## The gate

`VERIFIED_EMULATOR_PAIRS` in `src/pokeagent_bench/core.py` gains two pairs, and both point at this note.

1. PyBoy RS 0.1.5 recorded under 0.1.7. The Haiku rerun and 10 of the 58 set-up fixtures recorded 0.1.5.
2. PyBoy RS 0.1.1 recorded under 0.1.7. The published traces and the other 48 set-up fixtures recorded 0.1.1.

Both pairs name the Linux x86_64 builds. The 0.1.1 to 0.1.5 pair stays. Resume keeps the exact build rule, so a run paused under 0.1.5 resumes only under 0.1.5. No artifact was retagged or recorded again.

## Replay proof

Every replay below ran `scripts/verify_emulator_pair.py` with no check relaxed, except where a step names the one check it skipped. A replay passes only when every action's frame count, screenshot hash, evidence and awards match the recorded log, and the final score, action hash chain and trace head match too.

### Haiku rerun bundles

The 46 Short runs and the Long run of the Claude Haiku 5.5 rerun on `v0.37.3` were recorded under 0.1.5. They were replayed under the old pins and the new pins at the same time, one process each, on the same machine.

- 47 of 47 pass under both, 1,482,130 frames and 55,200 actions. Every row is the same under both builds, apart from its time.
- The Long run is 111,864 frames, 4,192 actions and a score of 13 under both.

Both bundles also pass `pokebench verify` on this branch under 0.1.7, with this checkout's harness added to the accepted list in that process only. Short verifies 46 of 46 cells and Long 1 of 1. Each report equals the report stored with the bundle in every field except `harness`, which names this checkout. The bundle hashes are unchanged, `538f2e2e06ec` for Short and `aaaf55b31c3a` for Long.

### Published traces

The 16 Long runs and 400 Short runs (focused-pass-v056, main-v066-astra and main-v067-fable) were recorded under 0.1.1. They were replayed six at a time under 0.1.7. The Short runs were then replayed again under the old pins with the same code, as a control.

- 16 of 16 Long runs pass, 12,930,007 frames in total. The largest is long-v072-astra-8k, with 2,222,534 frames, 80,799 actions and a score of 710. The [0.1.5 note](pyboy-rs-015.md) shows the same 16 identical under 0.1.5, so each matches its record under both builds.
- 300 of 400 Short runs pass under 0.1.7, 6,119,911 frames and 223,099 actions.
- The control gives the same 400 rows under 0.1.5 as under 0.1.7, field for field apart from time. 300 pass under both.

The other 100 Short runs are refused under both builds before any frame runs, so the emulator plays no part in it.

1. 80 are preparation cells. Their tasks left the catalog when Short dropped them, so replay stops with "Unknown catalog task".
2. 20 stop with "The catalog specification changed since this run started". These are the 18 focused-pass-v056 cells the 0.1.5 note lists for the same reason, plus cell-0046 of main-v066-astra and main-v067-fable.

As in the 0.1.5 note, all 100 were replayed again under both builds with only the specification check skipped.

- The 20 pass under both, identically, 508,311 frames and 19,907 actions.
- The 80 still stop before any frame under both, now with "Unsupported objective or unexpected fields", because the preparation objective left the code with the tasks.

So 320 of the 400 Short runs replay identically under 0.1.5 and 0.1.7, and the other 80 cannot be replayed by the current code under either build.

An earlier sweep of these 400 under 0.1.5 on November 12 passed 376. It ran on code from before November 14, when Short dropped the preparation tasks in 0.37.0. That sweep was left as it is, and this branch does not change the catalog.

### Fixtures

Each of the 58 set-up fixtures in the rerun data was loaded in a fresh process under both builds and run for 60 frames with no input. The screen after frames 1, 2 and 60, the work RAM and the saved state after frame 60 are identical in all 58.

## Speed and memory

These figures were measured on the Haiku bundles, one process per build, run side by side on one machine at nice 10 with other work running. Seconds count replay time only.

| Build | Frames per second | Actions per second | Peak memory |
| --- | --- | --- | --- |
| PyBoy RS 0.1.5 and Core 0.12.0 | 835.9 | 31.13 | 151.0 MB |
| PyBoy RS 0.1.7 and Core 0.12.3 | 839.9 | 31.28 | 125.6 MB |

Peak memory drops by 25 MB. Replay speed is flat because most replay time is spent outside the emulator. Plain ticking, 30,000 frames from the battle-elite-four-no-items fixture with no checks around it, runs at 13,391 frames per second under 0.1.5 and 14,191 under 0.1.7, 6% faster, with the same final state. Replay runs at about 840.

In the 0.1.7 sweep, the largest Long run peaked at 700.7 MB, and each process averaged 690 frames per second with six running.

## Checks

1. The full test suite passes, 1122 passed and 12 skipped. `ruff check .` is clean.
2. All five wheel hashes in `pyproject.toml` and the Core wheel hash match the SHA256SUMS of PyBoy RS v0.1.7 and pokecore-v0.12.3.

This change edits `core.py`, so the harness source hash differs from the accepted 0.37.3 entry. `pokebench verify` refuses on this checkout until a release adds its own accepted entry.
