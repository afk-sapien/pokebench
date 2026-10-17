# Gen 1 catalog runtime

The catalog now has 51 executable task definitions across six categories: eight navigation tasks, twelve battle tasks, ten menu operations, ten preparation tasks, ten objectives and one full-game campaign. The protocol is `red-v0.50-catalog-runtime`.

## What a task runs

Each task has a frozen native starting state, a concrete player instruction, a fixed action policy and a private evaluator. Starting-state facts, setup provenance and state hashes are recorded beside each private fixture. The fixture builders only modify setup copies. Scored gameplay advances through native controller inputs.

Menu operations enforce `manual-menu-v1`. A model cannot enable item, shopping, switching, dialogue or navigation shortcuts for those tasks. Strategy and campaign tasks retain mechanical shortcuts. The tested skill and policy are saved in every result manifest.

The 40 focused task graders check actual game state and, where needed, observed transitions. Examples include acquiring then delivering the parcel, capturing and training the same Abra before Misty, depositing and withdrawing the requested individual, and withdrawing a Potion before using it. A milestone needs confirming game frames. Existing completed state is not awarded again.

The full-game campaign starts in Red's bedroom and uses one continuous attempt. Its 50 milestones total 1,000 points. Hall of Fame registration completes the task even if optional collection bonuses remain. Milestones retain their actual order and cumulative frames, decisions, actions, tokens and time. Checkpoints preserve the evaluator's event history. Party and resource profiles are saved at milestones and at the current endpoint. Diagnostic values without verified telemetry are marked unavailable, not zero.

## Preparation is separate from battle play

The model chooses a bounded sequence of preparation operations using its visible party, storage and inventory. Those operations run through native Core menus. Its final party and supplies are frozen as a submission. The evaluated model never chooses battle actions in the assessment.

The assessment runs the same fixed controller for every submitted setup, across registered opponent starts and timing offsets. Multi-battle assessments carry remaining HP, PP and supplies forward. The uncertain-opponent task includes all three native Champion rosters. Each trial saves its result and replay inputs.

A fixed controller is not an optimal-play oracle. Preparation reports its observed win rate. A binary pass threshold remains unset until reference preparations establish a useful cutoff. Entry checks and controller smoke tests are distinct from model difficulty calibration. Timing offsets are reproducible starts, not a promise of statistically independent randomness.

## Run locally

Private fixture root on this machine:

```text
<private-data>/catalog-v1
```

Inspect and validate the installed fixture set:

```sh
uv run pokebench catalog --fixtures /path/to/catalog-v1
uv run pokebench catalog-validate --fixtures /path/to/catalog-v1 --rom /path/to/pokered.gb --output /tmp/catalog-validation.json
```

Run one task through an existing subscription transport:

```sh
uv run pokebench catalog-run \
  --fixtures /path/to/catalog-v1 \
  --task operations-heal-potion-target \
  --rom /path/to/pokered.gb \
  --game-data /path/to/game-data \
  --provider codex --model gpt-5.6-sol \
  --token-limit 100000 --output /path/to/new-run
```

Use `--provider claude --model MODEL` for Claude. `--variant` selects a registered alternative starting state. Supplying `--actions commands.json --reference` runs a zero-model native input trace and records its deterministic replay proof. Preparation actions use the preparation schema instead of raw buttons.

Run a selected comparison or omit `--tasks` for all focused PokeBench tasks. The full-game campaign now requires `--benchmark pokebench-long` in a separate batch:

```sh
uv run pokebench catalog-batch \
  --fixtures /path/to/catalog-v1 \
  --rom /path/to/pokered.gb --game-data /path/to/game-data \
  --models codex:gpt-5.6-sol claude:YOUR_MODEL \
  --tasks battle-prepared-gym operations-heal-potion-target \
  --repeats 1 --total-token-budget 1000000 \
  --output /path/to/new-comparison --dry-run
```

Remove `--dry-run` to execute. `--resume` skips recorded cells and continues remaining cells within the total batch ceiling. An interrupted cell requires inspection, rather than silently repeating already charged work. Individual native sessions retain the existing pause/resume command. Subscription token limits are enforced between model responses and cannot cancel an already charged response.

`catalog-report --batch /path/to/comparison` produces one result summary with task and category scores, token use, errors and coverage. Each task receives equal weight within its category even when it has more variants. Pending attempts are not counted as failures. Available category averages are exploratory, and coverage stays visible. Preparation win rates and campaign progress remain identifiable in the report.

## Local portal and results

The existing catalog page displays actual runnable status, starting variants and completed native reference proofs. It does not replace or hide historical model results. Refresh it with:

```sh
uv run python scripts/export_catalog.py \
  --output /path/to/all-results-preview \
  --fixtures /path/to/catalog-v1
```

New model trials must be run before making claims about difficulty or model ranking on these definitions. No broad paid model sweep is part of this implementation.

ROMs, generated game tables, native save states and private run artifacts remain outside the source package. The builders reconstruct local fixtures from the owner's available archives and existing source checkpoints. They do not imply that a public installation can run without supplying these assets.

## Local Core integration

This development checkout uses the immutable local Core `0.6.1.dev0` wheel in `vendor/`, selected by `tool.uv.sources`. It contains the shared PC acknowledgment and empty-box read fixes from the active `pokesim-core-gameplay` checkout. The wheel SHA256 is `6574b0482c6b2ed88ee4158bb708395df9cd308307914d15d3ec620306e4130f`. Run `uv sync --extra dev` to install the tested local configuration. The ordinary package metadata still names the last published Core wheel. Publishing a new benchmark release requires updating that published dependency once the shared Core fixes are released.

New fixture manifests record `release-all-before-first-tick-v1`. Raw emulator states omit queued host button releases. The loader queues releases before the first controller tick, without changing RAM or advancing the game. Replay applies the identical policy. Historical manifests retain their original input behavior. Full recovery checkpoints continue to preserve queued inputs directly through Core.


## Recovery and accounting update v0.51

New runs record `red-v0.51-catalog-recovery`. Task definitions, action policies and game scoring predicates are unchanged. Preparation infrastructure errors are excluded from ability scores, including legacy `preparation_error` records. Error metadata takes precedence over partial results without discarding known token charges.

Preparation calls persist a separate `model-usage.json` before interpreting the response. Malformed output retains its reported token count. A transport failure with unknown charges records `accounting_complete: false`. Batch reports expose accounting completeness alongside the known token total.

Before starting any new calls, batch resume checks all existing attempts. Running, paused and unfinished assessment attempts raise a recovery message instead of being skipped. Recover a paused gameplay attempt with the existing `pokebench resume --rom ROM --run CELL_DIRECTORY` command using its original runtime. In-flight or crashed attempts still require inspection of their checkpoint and usage. Incomplete token accounting must be reconciled before the batch can spend the remaining budget. Completed attempts retain their results and are skipped normally. This update does not launch or repeat any model trials.


## Benchmark separation v0.53

New runs record `red-v0.53-benchmark-tracks`. PokeBench and PokeBench Long are
separate execution and reporting tracks. [Current commands and scoring](benchmark-tracks-v053.md)
supersede the earlier combined catalog description. Task definitions and native
fixtures are unchanged by the separation. The current private fixture root is
`<private-data>/catalog-v2`.
