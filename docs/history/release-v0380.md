# Harder Short release v0.38.0

This tag is package 0.38.0, git tag `v0.38.0`, the first release of the benchmark version `red-v0.64-harder-short`. Short has 51 runs over 49 tasks: the 46 runs of `red-v0.63-short-guard`, unchanged, and the five harder tasks listed in [the harder Short note](harder-short-v064.md). It pins PyBoy RS 0.1.9 and PokeSim Core 0.12.4, as listed in [the 0.1.9 note](pyboy-rs-019.md). Claude Code 2.1.323 stays pinned.

## What changes for scoring

1. A Short result of this release is a `red-v0.64-harder-short` result, 51 runs over 49 tasks. It is ranked apart from `red-v0.63-short-guard` results, which are not rescored.
2. A finished `red-v0.63-short-guard` run folder can be topped up instead of run again. The topped-up folder holds `red-v0.64-harder-short`, and its bundle counts the same as a fresh 51-run bundle.
3. `verify` matches runs by task, variant and repeat, not by the folder a run sits in. A topped-up bundle and a fresh bundle of the same runs get the same score.
4. `verify` checks a bundle that holds exactly `red-v0.63-short-guard` as that version, so the published 46-run bundles keep their scores on this release.

## Top up a finished older Short run

Run the same `run --suite short` or `enter --suite short` command on `v0.38.0`, with the same output folder. Before the estimate it prints which version the folder holds and which runs `red-v0.64-harder-short` adds. `enter` still asks before the first model call.

- The 46 runs stay in `cell-0001` to `cell-0046` as they are. The five new runs get `cell-0047` to `cell-0051`, and only these start.
- The older plan is kept as `plan-red-v0.63-short-guard.json` next to the new `plan.json`.
- A folder whose runs no longer match this checkout, by task, variant, start state, task specification or limits, is not topped up.
- A setup from an older release gains the five starts from the fixture pack before the top-up, as `setup` would add them.
- A task paused on `v0.37.4` or older is finished on its own release first. The command stops before the estimate and prints the command for that release.

Each run keeps the manifest of the release it ran on, so a topped-up bundle holds runs from both releases. Every run must match an accepted entry, and each is checked against this checkout's start states, task specifications and limits.

## How verify reads a Short bundle

The task list must be the complete current suite, or exactly an older recorded Short version whose runs this checkout still holds unchanged. In both cases the runs, their start states, task specifications and limits come from the verifier's own plan. The bundle plan only says which folder holds each run. Each folder name must have the form `cell-NNNN` and can be named once, and a run read from the wrong folder fails its start state or scenario check. The suite version in the report comes from the verifier's plan.

## Large inspections no longer stop a run

In the Elite Four and Champion saves, inspecting storage gives about 62,000 bytes of compact JSON. On `v0.37.4` and earlier the whole packet had to fit in 64,000 bytes. A storage inspection that came on a segment snapshot or a busy battle update stopped the run with an observation budget error, before any model call. The task ended as an evaluation error, and the bundle could not be packed until that task ran again. The random player hit this in `battle-elite-four-no-items-no-faint` during the release check.

On `v0.38.0` the inspection keeps its own 64,000 byte bound and the rest of the packet its 32,000 byte bound, so such a packet reaches the model. A packet that fit before renders and passes as before, and an inspection over its own bound still stops the run. Verify replays inputs and does not render packets, so scoring is unchanged. No published result was affected. Every published result is a complete bundle, and none of the published Short runs inspected storage in these saves.

## Other changes since v0.37.4

1. A Codex usage limit or capacity refusal with no model output pauses the task and names the reset, like the Claude one.
2. A task stopped by a provider error after the model may have replied resumes from its last checkpoint with the same command, without moving its folder.
3. A run paused on another release is sent back to that release with its exact `uvx` command.
4. The fixes from the outsider test of the submission path: the placeholder handle is refused, an OpenAI compatible endpoint is checked before the first call, a refused connection pauses instead of failing the task, and a suite stopped by a failed or paused task exits 1.

## Runs from earlier releases

The entries for `v0.36.0` to `v0.37.4` stay in [accepted_harness.json](../../src/pokeagent_bench/accepted_harness.json) unchanged, and the `v0.38.0` entry is added after them. A run paused on `v0.37.4` or older is resumed on that release, because `v0.38.0` changes the emulator, the core and the harness.

## Checks

1. The three published `red-v0.63-short-guard` bundles, Claude Haiku 5.5, GPT-5.6 Terra and Claude Sonnet 5.5, verify on the `v0.38.0` tree from their own `v0.37.4` runs under the `v0.37.4` entry. This ran before the inspection fix, which changes no code that verify runs. Each report names `red-v0.63-short-guard`, 46 runs over 44 tasks, and its summary and every run equal the published report apart from wall time. The scores stay 62.8, 62.9 and 63.1, and the bundle hashes are unchanged.
2. A copy of the published Claude Sonnet 5.5 `red-v0.63-short-guard` folder was topped up with `run --suite short`. Only the five new runs started, in `cell-0047` to `cell-0051`. The check calls no model, so the free random player played them under the Sonnet model name. The same 51 run folders were also laid out as a fresh 51-run plan lays them out, which puts 40 runs in another folder. Both bundles verify as `red-v0.64-harder-short`, 51 runs over 49 tasks, with the same score of 58.4. The summaries are equal, every run is equal apart from its folder, and the 46 older runs keep their published scores. This score mixes real and random runs and is not a result.
3. In that check the random player sent a 72,631 byte packet with a storage inspection in `battle-elite-four-no-items-no-faint`. `v0.37.4` refused such a packet, and on `v0.38.0` the run finished.
