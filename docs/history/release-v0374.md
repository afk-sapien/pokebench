# New emulator and core pins v0.37.4

This tag is package 0.37.4, git tag `v0.37.4`, under the same harness name `red-v0.63-short-guard`. It pins PyBoy RS 0.1.7 and PokeSim Core 0.12.3, in place of PyBoy RS 0.1.5 and PokeSim Core 0.12.0. The task specs, the start states, the fixture pack, the prompts, the run limits and the way a run is played and scored are those of `v0.37.3`. Claude Code 2.1.323 stays pinned.

## Resume a paused run on its own release

A run paused on `v0.37.3` or older must be resumed on that same release. Do not resume it on `v0.37.4`.

Resume needs the same emulator, the same core and the same harness code the run started with. `v0.37.4` changes all three, so it refuses to resume a run started on an older release. Run the older release's `enter` command again, with its own tag, to finish the run. A run that finished on an older release packs and verifies as before.

## What changes

1. `pyproject.toml` and `uv.lock` pin the PyBoy RS 0.1.7 wheels and the PokeSim Core 0.12.3 wheel by hash.
2. Replay accepts two more build pairs, a run recorded under 0.1.1 or 0.1.5 replayed under 0.1.7. Each pair names [the 0.1.7 note](pyboy-rs-017.md), which holds the replay sweep behind it.
3. Nothing a run records, plays or scores changes. Every replayable recorded run gives the same frames, screens, evidence and score under 0.1.7 as under 0.1.5.

## Runs from earlier releases

The entries for `v0.36.0`, `v0.37.0`, `v0.37.1`, `v0.37.2` and `v0.37.3` all stay in [accepted_harness.json](../../src/pokeagent_bench/accepted_harness.json), and the `v0.37.4` entry is added after them. A finished `v0.37.1`, `v0.37.2` or `v0.37.3` run is checked on the `v0.37.4` checkout. Both bundles of the Claude Haiku 5.5 rerun, run on `v0.37.1` and `v0.37.2` and packed on `v0.37.2`, verify on the `v0.37.4` tag, Short 46 of 46 cells and Long 1 of 1, with unchanged bundle hashes.
