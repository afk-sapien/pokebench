# PokeBench v1 beta release protocol

This prospective evaluation starts after development. Historical runs are not imported into its scores. The public website retains a clearly labeled development comparison while the release evaluation accumulates matched coverage.

## Registration and coverage

The active catalog has 28 tasks. Twenty-two are eligible for scoring and six new decision tasks are experimental. Five retired trivial tasks remain in the local audit history. A fresh registration samples three timing offsets per task with seed 20261005, before any release model calls. These 84 states are shared by every registered model.

Timing offsets are paired starting conditions, not statistically independent random seeds. No failed model outcome is replaced with a more favorable start. Initial-state checks ensure the intended task has not already completed. Earlier reference victories establish feasibility at the source checkpoint. They do not prove that every fresh timing variant is winnable under every strategy.

The model inventory contains seven previously evaluated OpenAI IDs and nine non-Fable Claude IDs advertised by the official Claude Code CLI. Availability is recorded separately from successful execution. Three Claude models passed transport smoke tests. An unavailable registered model produces an infrastructure issue, not a gameplay loss. Fable is excluded because subscription inclusion is unclear.

## Budget and execution

The global authorization is **50,000,000 reported tokens** across the new evaluation. Each task retains its registered per-attempt allowance. All models receive the same task limits. The full planned matrix is larger than this global authorization. It is intentionally staged, and unfinished cells stay pending.

Tasks run in a fixed priority order, with all three variants and rotated model order within each task. This produces complete matched tasks earlier than cycling once through the entire catalog. An allowance reserve is checked before starting each attempt. Usage includes input, output and cached input counted once. No credit purchases or paid API fallback occur automatically. Unknown usage stops the sweep for infrastructure review.

Each call uses the bounded gameplay policy, eight-turn segments and a 12,000-token context threshold. Context resets use deterministic observations and agent notes, with no model-generated summaries. Requested effort is medium. Providers interpret effort differently, and Haiku lacks an adjustable effort control. Exact model and effective settings remain in the result provenance.

One in-flight provider response can exceed an admission estimate. The token ceiling is a scheduling and accounting guard, not a provider-side hard billing cap. Subscription fees are not allocated to individual runs. API-equivalent cost estimates, where available, are labeled separately.

## Scoring and uncertainty

A task contributes to the new aggregate only when every registered model has finished every registered variant and every replay verifies. Each eligible task has equal weight. Pending cells and infrastructure errors are not counted as losses. The six experimental tasks are displayed without affecting the main score.

Per-task wins, attempts and descriptive Wilson intervals accompany the point estimates. Three timing conditions provide limited evidence and do not justify small rank differences or claims of independent sampling. Report both token use and success, because a short failed run is not an efficient successful run.

## Local reproduction

Install dependencies, supply a matching ROM, build the locally validated `red-ability-v7` suite using the task preparation scripts, and provide the same locally generated game-data catalog. See the task-specific setup documents. Full fixture preparation currently requires curated source checkpoints, so a clean install alone cannot reproduce every released task. The release publishes checkpoint hashes and provenance, not ROMs or save states.

```sh
PYTHONPATH=src uv run python scripts/pokebench_release.py prepare \
  --suite /private/red-ability-v7 --rom /private/red.gb \
  --root /private/release --variants 3
PYTHONPATH=src uv run python scripts/pokebench_release.py freeze \
  --root /private/release --models /private/models.json \
  --budget 50000000 --game-data /private/game-data
PYTHONPATH=src uv run python scripts/pokebench_release.py run \
  --root /private/release --rom /private/red.gb --game-data /private/game-data
```

`models.json` is an array of objects with `model`, `provider` and `effort` fields. Providers are `codex` or `claude`. Use exact available IDs. Freeze hashes the runtime, catalog, core, ROM, fixture registration and protocol. Edits require a new registration. Raw local attempts are retained for audit. Offline replay makes no model requests.

## Release status

The immutable machine-readable protocol and sanitized release summary are the authority for planned coverage, completed attempts, consumed tokens and pause reasons. The technical report labels the controlled evaluation pending until those results are available. Development and prospective results must never be silently pooled.

## Parallel execution amendment

At the owner's request, execution can switch to four isolated trial processes, with at most two per provider. A single coordinator retains the release lock, writes shared status, and reserves each active trial's entire token ceiling plus the registered in-flight reserve. Previously spent tokens remain in the same 50-million-token ledger. Unused reservations return only after a worker finishes with valid accounting and verified replay.

Trials stay within the first unfinished task and starting variant. The earliest pending model with a free provider lane starts next. This changes dispatch order and wall-clock conditions, so the coordinator records a hashed `execution-amendment-001.json` alongside the untouched original protocol. Gameplay prompts, model settings, starts, scoring and per-trial limits remain frozen. Timing comparisons across the switch are not controlled because provider throttling can affect concurrent runs.

The serial trial is checkpointed at a complete decision boundary and resumed with its original conversation and accumulated usage. Completed attempts are retained. Any infrastructure failure stops new admissions while already reserved workers finish. There are no automatic model retries. The frozen runtime stays in the release folder and the external scheduling script has its own recorded hash.

```sh
uv run python scripts/parallel_release.py run \
  --root /private/release --rom /private/red.gb --game-data /private/game-data \
  --workers 4 --per-provider 2
```

A reviewed failed attempt may be quarantined explicitly with `--quarantine-cell CELL_ID`. It stays an evaluation error, is never retried automatically, and contributes no success or failure score. Its entire trial ceiling plus the in-flight reserve remains charged against the shared authorization. Missing usage stays marked incomplete, and the conservative budget hold is separate from measured token counts. Each reviewed continuation receives a new hashed execution amendment. Any new unreviewed error still stops admission.
