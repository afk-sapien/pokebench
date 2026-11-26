# Harder Short red-v0.64

The benchmark version `red-v0.64-harder-short` adds five harder tasks to Short. The owner approved adding them on 25 November 2026. Short now has **51 runs over 49 tasks**, up from 46 runs over 44 tasks under `red-v0.63-short-guard`. This version is not released yet. It has no tag and no entry in [accepted_harness.json](../../src/pokeagent_bench/accepted_harness.json), and the package version stays 0.37.4.

## Scores belong to a suite version

[short_suites.json](../../src/pokeagent_bench/short_suites.json) records each Short suite version with its benchmark name, run count, task count and each run's task, variant, `evaluation_spec_sha256` and `fixture_sha256`. A Short score belongs to the version whose runs it holds exactly.

| Version | Runs | Tasks | Runs made on it |
| --- | --- | --- | --- |
| `red-v0.63-short-guard` | 46 | 44 | Haiku, Terra and Sonnet |
| `red-v0.64-harder-short` | 51 | 49 | None yet |

Runs made on `red-v0.63-short-guard` stay valid for that set and are ranked separately. They are not rescored. The 46 runs of the older set are kept unchanged in the new one, with the same task specification and start state digests.

The suite estimate, the run summary, the bundle summary that `submit` prints and the verified report each name the version with its run count, for example `Suite version red-v0.64-harder-short, 51 runs over 49 tasks.` The verified report takes the version from the verifier's own plan, never from the bundle. Runs that match no recorded version print `Suite version: none` and are not a ranked result. `tests/test_suite_versions.py` checks that the current catalog matches the current entry.

## The five tasks

| Task | Category | Milestones | Reference decisions | Decision cap |
| --- | --- | --- | --- | --- |
| `navigation-vermilion-gym-switches` | Navigation | 3 | 70 | 350 |
| `navigation-safari-zone-secret-house` | Navigation | 3 | 73 | 370 |
| `objectives-saffron-gate-drink` | Quests | 3 | 68 | 340 |
| `battle-elite-four-no-items-no-faint` | Battle | 5 | 109 | 550 |
| `battle-champion-no-items-no-faint` | Battle | 2 | 22 | 110 |

Each is a milestone task in the released navigation, battle and quests catalogs, so `run --suite short` plans it and its manifest records the track `pokebench`. Each catalog entry pins its start state digest and its scripted reference: the input digest and count, the frames and the decisions. The decision cap is five times the reference decisions, rounded half up to two significant figures, and the token cap is 15,000 tokens per allowed decision. The separate candidate catalog and its code are gone. See [the catalog](../catalog/README.md#harder-short-tasks) for the starts and the two stop rules, `no_faint` and `fail_on`.

## Setup

The five starts and their reference proofs ship in the fixture pack, which now holds 93 start states in 468 files and is 327,591 bytes. A fresh `setup` builds them with every other start. A `data/fixtures` folder from an older release gains the starts it lacks when `setup` runs again, or when `run --suite` plans a new run, and keeps the starts it has. The whole pack is checked against its hash first. No user runs a separate script.

The pack builder now drops a temporary folder path whole. The reference proofs record the local folder of the reference run, which is never read, and the 12 milestone proofs held a temporary path. Each now reads `private:`. No start state, task specification or pin changes.

## Budgets

Short keeps its 60M reference budget. The reference budget only prints a warning, and each task keeps its own cap, so the five tasks cannot take an allowance from another task. The worst case, the sum of the caps, grows from 279.6M to 305.4M.

## Checks

The five starts were built again and each reference was replayed on the pins of main, PyBoy RS 0.1.9 and PokeSim Core 0.12.4. All five completed with a full score, the replay matched, and the start, input digest, input count, frames and decisions equal the catalog pins. A setup unpacked from the new pack plans exactly the 51 runs of `red-v0.64-harder-short` with no task held back.
