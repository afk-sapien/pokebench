# PokeBench and PokeBench Long

PokeBench measures focused gameplay skills from fixed checkpoints. PokeBench Long
measures sustained progress through one full game. They are separate benchmarks
using the same emulator, controls, observation framework and result archive.

| Benchmark | Scope | Main result |
| --- | --- | --- |
| PokeBench | 47 focused tasks plus one inventory variant across five categories | Per-task outcomes and category scores |
| PokeBench Long | One continuous start-to-Champion run | Champion completion and progress across 50 milestones, up to 1,000 points |

Long also records token use, actions, frames, elapsed time and party/resource
profiles. A partial campaign receives earned milestone points but is not a
Champion completion. Its progress score never enters the focused-task average.
Preparation tasks remain in PokeBench and report fixed-controller assessment win
rates. Inventory variants continue to share their parent task weight.

## Inspect

```sh
uv run pokebench catalog --benchmark pokebench
uv run pokebench catalog --benchmark pokebench-long
```

The default CLI catalog is PokeBench. The local exported pages are `catalog.html`
and `pokebench-long.html`, with separate downloadable JSON definitions. The old
campaign anchors on the catalog page redirect to the Long page.

## Run separate batches

These examples only create dry-run plans. Remove `--dry-run` to execute within
the chosen token ceiling. Use separate output directories and budgets.

```sh
uv run pokebench catalog-batch \
  --benchmark pokebench \
  --fixtures /path/to/catalog-v2 --rom /path/to/pokered.gb \
  --game-data /path/to/game-data --models codex:MODEL \
  --total-token-budget 1000000 --output /path/to/short-comparison --dry-run

uv run pokebench catalog-batch \
  --benchmark pokebench-long \
  --fixtures /path/to/catalog-v2 --rom /path/to/pokered.gb \
  --game-data /path/to/game-data --models codex:MODEL \
  --total-token-budget 5000000 --output /path/to/long-comparison --dry-run
```

New batches default to PokeBench and reject campaign tasks unless Long is selected.
A Long batch rejects focused tasks. `--resume` retains the recorded selection and
cannot switch an existing batch to the other benchmark. `catalog-run --task`
remains available for explicitly selecting an individual task.

`catalog-report --batch DIRECTORY` separates model summaries by benchmark. It
also separates older mixed batches when reporting them, retaining every recorded
attempt without altering raw results. For Long, it reports campaign progress,
Champion completions and individual run statistics. There is no combined rank.

This is protocol `red-v0.53-benchmark-tracks`. Game scoring predicates, starting
saves, old model results and reference replays have not changed. No model calls
are made by catalog export or dry-run planning.


## Current pilot follow-up

The v0.54 pilot fixes and measured menu allowance are documented in
[catalog-pilot-v054.md](catalog-pilot-v054.md). Use the current private fixture
root `<private-data>/catalog-v4` for new catalog runs.
Historical `catalog-v2` and `catalog-v3` artifacts remain unchanged.
