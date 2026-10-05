# Pokemon ability suite v1

Package 0.27.0 and benchmark red-v0.37-experimental add `red-ability-v1`, a
nine-task development suite. It uses the existing gameplay observation and menu
shortcut policy, with Core 0.1.4. Models receive the same saves, tools, objectives,
reasoning effort and task budgets. Each task starts with fresh model context.

| Task | Difficulty | Token ceiling |
| --- | --- | ---: |
| Get a starter | Easy | 1,000,000 |
| Win a wild battle | Easy | 250,000 |
| Heal at the Pokemon Center | Easy | 500,000 |
| Collect and deliver Oak's Parcel | Medium | 1,500,000 |
| Defeat Brock | Medium | 500,000 |
| Recover the party with items | Medium | 250,000 |
| Defeat Agatha | Hard | 750,000 |
| Defeat Lance | Hard | 750,000 |
| Become Champion | Hard | 3,000,000 |

The total ceiling is 8.5 million reported tokens per model. The initial sweep
registers one attempt each for Luna, Terra and Sol, for 27 attempts and a maximum
of 25.5 million tokens. Input, including cached input, and output count toward
the cap. Success ends a run early. There are no automatic retries or usage-credit
resets. Infrastructure errors stop the batch and stay visible.

## New checkpoints

Agatha and Lance begin at their own first battle menu, extracted by replaying
the existing offline PokeSim League reference. Party health, levels, PP, status,
items and prior League progress remain exactly as reached in that reference.
These are not artificially refreshed teams. Every model receives the identical
saved state for each task. Their goal is only that named trainer's victory.

Item recovery starts in the League room from the retained Sol decision 150,
with an injured, afflicted and partly fainted party. The goal is full HP and
no status conditions for every original party member, in that room. Replacing
a Pokemon or blacking out invalidates success. PP recovery is not required.
The agent selects the items and targets. Menu shortcuts carry out its selections.

Curation uses controller inputs and checkpoint extraction. It introduces no
RAM edits, added items or grading flags into model observations. Every task must
pass a fresh successful reference, independent controller replay and a no-input
negative check before models run. ROMs, checkpoints and private traces stay local.
The builder requires the retained development archives documented in its source.

```sh
PYTHONPATH=src .venv/bin/python scripts/prepare_ability_fixtures.py \
  --root /path/to/pokeagent-bench --rom /path/to/pokered.gb \
  --game-data /path/to/game-data --output data/new-ability-curation
uv run pokeagent suite prepare --suite-id red-ability-v1 \
  --rom /path/to/pokered.gb --bindings data/new-ability-curation/bindings.json \
  --output data/new-ability-suite
uv run pokeagent suite run --suite data/new-ability-suite \
  --rom /path/to/pokered.gb --game-data /path/to/game-data \
  --models gpt-5.6-luna gpt-5.6-terra gpt-5.6-sol --repeats 1 \
  --total-token-budget 25500000 --output data/new-ability-comparison
```

## One ranking page

The canonical local page is `pokemon-benchmarks.html`, served alongside the
existing results and replay files. A compact model leaderboard shows score,
coverage and token usage. Category filters narrow the comparison. The benchmark
list supports search, difficulty filters, sorting and ten tasks per page.
Selecting a model or benchmark opens detailed outcomes and recorded replay links.
Adding benchmarks grows the list without adding leaderboard columns.

The default view combines available evidence across all benchmarks. The comparison
selector preserves each original experiment for inspection. JSON and CSV exports
remain available for each comparison. The page refreshes its data in place,
preserving the selected filters, page and open detail view.

The portal reads existing reports and does not change evaluation execution.
Start its publisher separately from the benchmark supervisor:

```sh
PYTHONPATH=src .venv/bin/python scripts/publish_portal.py \
  --config data/portal-config.json \
  --output data/reviews/pokemon-benchmarks.html --watch-seconds 20
```

The configuration is an array of comparisons. Each entry provides `id`, `label`,
`report`, `suite` and `batch` paths. Report and suite hashes must match. Keep
report exports, replay files and the portal in the same served directory.
The supervisor still writes `pokemon-leaderboard.json` as the current comparison
feed. The portal combines separate feeds for browsing without pooling scores.

Score is the equal-weight average of per-task completion rates. All registered
repeats count. Equal scores receive tied ranks, regardless of token usage.
Rankings appear only when all models have completed identical task coverage and
all completed runs have verified replays. Pending tasks and infrastructure errors
are not scored as gameplay failures. Token usage is an efficiency measure shown
separately from ability. Failure and interrupted-run tokens remain in totals.

This is a preliminary ranking of performance on these nine saves, not a universal
measure of Pokemon skill. Several tasks involve battles, and the League task
shares opponents with isolated tests. One repeat gives no reliable estimate of
run-to-run variance. Later repetitions should be preregistered for every model,
not selectively rerun to improve a score.

Raw prompts, observations, model decisions, usage, screenshots, controller traces,
initial and final states, results and replay checks remain in the batch directory.
A frozen source snapshot, locked dependency environment, fixed Core version,
fixture hashes and registered cell plan make the comparison identifiable.
Earlier basic and League experiments remain available as separate archives.
They are not mixed into this ranking because their settings differ.


## Five additional tasks

`red-skills-v1` adds five independently verified checkpoints. `red-ability-v2`
contains the original nine tasks plus these five. The original definitions,
budgets and saved trials remain unchanged.

| Task | Start | Success | Difficulty | Token cap |
| --- | --- | --- | --- | ---: |
| First capture | First wild battle with one owned starter and Poké Balls | Catch a wild Pokemon and add it to the party | Easy | 250,000 |
| Return delivery | Outdoors in Viridian carrying Oak's Parcel | Deliver it and receive the Pokedex | Medium | 750,000 |
| Lorelei | First battle menu against Lorelei | Verified Lorelei victory | Hard | 750,000 |
| Bruno | First battle menu against Bruno | Verified Bruno victory | Hard | 750,000 |
| Champion duel | First battle menu against the final rival | Win and complete Hall of Fame registration | Hard | 1,000,000 |

The battle checkpoints inherit the actual party, HP, status, PP and supplies from
the successful archived League controller trace. They are not refreshed or edited.
The return delivery is shorter than the original collection-and-return task.
The Champion duel starts after the Elite Four, unlike the full League campaign.
Capture begins at a battle menu, separating capture decisions from navigation.
These overlapping subskills are intentional diagnostics, not independent estimates
of general ability. The expanded suite changes task weighting and must be ranked
as a separate version.

Every checkpoint includes its source state and trace hashes, action offset,
starting screenshot, successful controller replay and unsuccessful no-input
replay. No model tokens are used to construct or verify checkpoints. Successful
reference runs are fixture evidence, never model results.

```sh
PYTHONPATH=src .venv/bin/python scripts/prepare_skill_fixtures.py \
  --root . --rom /path/to/pokered.gb --output data/new-skill-curation
uv run pokeagent suite prepare --suite-id red-skills-v1 \
  --rom /path/to/pokered.gb --bindings data/new-skill-curation/bindings.json \
  --output data/new-skills
uv run pokeagent suite prepare --suite-id red-ability-v2 \
  --rom /path/to/pokered.gb --bindings data/new-skill-curation/expanded-bindings.json \
  --output data/new-expanded-suite
uv run pokeagent suite run --suite data/new-skills \
  --rom /path/to/pokered.gb --game-data /path/to/game-data \
  --models gpt-5.6-luna gpt-5.6-terra gpt-5.6-sol --repeats 1 \
  --total-token-budget 10500000 --output data/new-skills-comparison
```

The five-task sweep reserves up to 3.5 million tokens per model, or 10.5 million
across these three models. The fourteen-task sweep reserves 12 million per model.
Adding the catalog to the portal does not start paid or subscription model runs.


## New-task sweep protocol v0.38

The five-task sweep uses one Luna, Terra and Sol attempt per checkpoint, with the
registered 10.5 million total token ceiling. Its source, dependency lock, Core,
saves and prompts are frozen before launch. Model traces and replay audits are
retained. Results stay separate from v0.37 and earlier runs.

In v0.37, an empty action list without a look-back request raised a provider error
after the model call, dropping known token usage and stopping the batch. v0.38
returns that decision and usage to the existing runner validation path. It records
tokens, performs no controller action and reports the invalid batch length. Three
consecutive invalid decisions end that trial as `invalid_model_response`. This
uses the existing invalid-action rule. It does not infer a game action or accept
the model's claim of success. Genuine provider and accounting errors still stop
the sweep. Earlier trials are preserved without rewriting their outcomes.


## Five adventure tasks in v0.39

`red-adventure-v1` adds five tasks. `red-ability-v3` is the nineteen-task catalog.
Existing suites and model results retain their original definitions and versions.

| Task | Starting situation | Success | Difficulty | Token ceiling |
| --- | --- | --- | --- | ---: |
| Buy ten Poke Balls | Viridian outdoors after parcel delivery, without balls | Gain at least ten balls, spend at least their shop price, close menus inside the Mart | Easy | 500,000 |
| Cross Viridian Forest | Southern forest entrance | Reach Pewter City with overworld control | Medium | 1,000,000 |
| Reach Cerulean through Mt. Moon | Western cave entrance | Reach Cerulean City with overworld control | Hard | 1,500,000 |
| Win a fossil | Super Nerd battle menu in Mt. Moon | Acquire either fossil and finish the interaction | Medium | 500,000 |
| Defeat Misty | Misty's battle menu before the Cascade Badge | Earn the verified Cascade Badge | Medium | 750,000 |

The new navigation, shopping and acquisition objectives reject completion during
battle or menus. A blackout permanently disqualifies those tasks, including after
save/resume. Shopping requires both an inventory gain and a corresponding drop
in money. Obtaining a fossil requires that neither target fossil was owned at the
start. Two consecutive qualifying game frames confirm success. Evaluator evidence
stays private, and agents receive the ordinary gameplay observations and task text.

The early checkpoints come from the archived controller trace used by previous
fixtures. Later checkpoints come from PokeSim controller play starting at the
verified Brock reference's final state. The simulator operates on a separate
emulator and read-only RAM interface. There are no memory edits, injected supplies,
or changes to the PokeSim checkout. Party health and supplies remain as played. The Mt. Moon fixture uses the last
settled western entrance in the recorded successful traversal before first reaching
Cerulean. An earlier reference that blacked out was rejected and retained privately.
Overworld checkpoint selection waits for map transitions to settle.
Each task has a successful replay and a no-input negative replay.

These tasks overlap with existing subskills. The nineteen-task catalog is a new
score definition, not a way to pool scores across different historical protocols.
Creating and validating fixtures does not run subscription models.

```sh
PYTHONPATH=src .venv/bin/python scripts/prepare_adventure_fixtures.py \
  --root . --rom /path/to/pokered.gb --pokesim /path/to/pokesim \
  --output data/new-adventure-curation
uv run pokeagent suite prepare --suite-id red-adventure-v1 \
  --rom /path/to/pokered.gb --bindings data/new-adventure-curation/bindings.json \
  --output data/new-adventure-suite
uv run pokeagent suite combine --suite-id red-ability-v3 \
  --sources data/red-ability-v2 data/new-adventure-suite \
  --output data/new-nineteen-task-suite
```

Combination imports unchanged fixtures and their existing replay proofs from
validated suites with matching ROM and Core identities. It rejects missing,
duplicate or changed tasks and preserves source suite hashes. No model outcomes
are copied into the new comparison. The five new tasks reserve at most 4.25 million
tokens per model, or 12.75 million for one Luna, Terra and Sol attempt each.


## Combined analysis v1

The portal defaults to `combined-exploratory-v1`, covering the largest verified
catalog. This is an exploratory cross-version analysis, not a claim that all tasks
were run under one frozen harness. Per-task details record the selected comparison,
benchmark version, Core version, source hash, save and replay links.

The publisher configuration lists comparisons in explicit newest-first priority.
For each benchmark it selects the newest comparison where at least one attempt
has started. If none have started, it shows the newest registered comparison.
A registration with no started attempts does not hide older observations. Once a
new attempt starts, the whole task switches to that comparison for every model.
This selection never depends on pass rate. A new failure or infrastructure error
does not fall back to an older success. Checkpoint hashes, objective, ROM and token
ceiling must match the catalog task. A changed checkpoint is not a substitute.

A benchmark enters the score only when all displayed models have finished the
same registered repeats with verified replays. Models share the same denominator.
Scores average completion rates within a task, then give each eligible task equal
weight. Missing, pending and infrastructure-error trials remain visible but exclude
that task from every model's score. Ordinary gameplay failures and token-budget
failures still count. Coverage is displayed prominently, and partial scores are
provisional. Category filters apply this rule within the selected category.

Each benchmark contributes once. Older copies are not additional points. Token
totals include all attempts selected for display, even when their task is not yet
scored. The combined JSON contains selected sources, eligibility and model scores.
The CSV includes source comparison, benchmark version and score inclusion for each
attempt. Original data and historical comparison views remain intact.

## All eight Gyms and difficult League in v0.40

`red-gyms-v1` registers one trial per model for nine tasks: Brock, Misty,
Lt. Surge, Erika, Koga, Sabrina, Blaine, Giovanni and a difficult full League.
Brock and Misty retain their existing checkpoint hashes, goals and budgets.
The six new gym fixtures start at the first battle menu against the correct
unbeaten leader, with a conscious party. Giovanni must be in Viridian Gym.
His earlier Rocket battles cannot satisfy this benchmark.

The new fixtures come from read-only archived PokeSim saves. The offline
simulation uses controller inputs to reach each leader and prove a win.
Every fixture has a successful replay and a no-input negative replay. Models
receive no reference commands or private evaluator flags.

The difficult League team is Pidgeot level 50, Charizard level 61, Lapras
level 58, Vileplume level 44, Raticate level 33 and Beedrill level 38.
It starts healthy with full PP, five Revives, one Elixer and no HP-restoring
potions. It has weak supporting members and poor moves on several Pokemon.
The team is taken from a natural archived PokeSim run, without RAM edits,
level changes or invented inventory. Existing archived nicknames are preserved.
Agents must not assign new nicknames.

Success means reaching Hall of Fame registration after defeating all four
Elite Four members and the Champion. As in the original League task, a
blackout does not invalidate the entire trial. The agent may recover and
retry within its original budget, with all play and usage retained. The
controller reference needed four League attempts and won with the same six
Pokemon. This establishes attainability, not a guarantee of a single-pass win.

Brock has 500,000 tokens, Misty and each new Gym have 750,000, and the
hard League has 3,000,000. Luna, Terra and Sol each receive the same saves,
medium reasoning effort, bounded eight-turn context and existing gameplay
menu shortcuts. The 27 trials have a combined ceiling of 26,250,000 tokens.
Unused tokens are not charged against the recorded usage. Subscription
limits can stop the sweep, and no usage reset is automatically redeemed.

`red-gym-additions-v1` contains the seven new tasks.
`red-ability-v4` expands the catalog to 26 unique tasks. The default combined
analysis incorporates the new results with equal weight per task, after all
three models finish a matched task. It preserves historical attempts and
labels mixed protocol results exploratory. The hard League remains distinct
from the original League, so neither result overwrites the other.

The v0.40 change adds fixtures and task registration only. It does not change
agent observations, available actions, prompts or context management.

## Completing the seven missing evaluations

The October 2 completion sweep selects only Sol's interrupted item-recovery
trial and the six unstarted Agatha and Lance trials. It uses the original
250,000-token item-recovery cap and 750,000-token battle caps. The maximum
new usage is 4,750,000 tokens. There are no extra repetitions or automatic
retries of gameplay failures.

`red-skills-completion-v1` contains these three existing tasks with unchanged
save hashes, objectives and budgets. Its comparison retains the original
completed Luna and Terra item-recovery records, byte for byte. Their origin,
manifest hash and result hash are recorded and the portal labels them as
earlier completed evaluations. The interrupted original Sol attempt remains
in the historical comparison. Seven new attempts complete the nine-cell
comparison without charging for another Luna or Terra item-recovery run.

This is an exploratory repair of missing coverage. Retained results use
v0.37 and new results use the corrected v0.40 runner. The combined analysis
continues to expose both versions and preserve the original raw records.

## Seven-model expansion on October 3

The full 26-task catalog now registers GPT-6 Astra, GPT-6 Sol, GPT-6 Luna and
GPT-5.5 alongside GPT-5.6 Luna, Terra and Sol. Each additional model runs
one trial per task at medium reasoning effort with the unchanged v0.40
observations, bounded context, controller tools and task-specific limits.
All four were present in the live subscription client's model inventory.

There are 182 registered model/task pairs. The comparison retains 76
completed evaluations with their original outcomes, manifests, controller
traces, usage and input-delivery audits. This includes gameplay failures.
Retained results are labeled and their source hashes are recorded. Three
retained original League results used Core 0.1.3, so the combined analysis
remains exploratory. All new trials use the pinned Core 0.1.4 runtime.

The four additional models contribute 104 new evaluations with a maximum
combined allowance of 95,000,000 tokens. The earlier Terra Lance trial
ended in a provider error and Sol Lance was never started. Those two gaps
are also registered, adding a maximum of 1,500,000 new tokens under the
prior authorization to complete missing evaluations. A gameplay failure
is a completed result and is not rerun. Previously consumed tokens remain
in cumulative analysis totals and are not new inference charges.

The main page displays all seven models together. Scores use only tasks
with matched completed coverage across all seven, so the ranking is
provisional as the new trials finish. The supervisor records every outcome,
verifies replays and publishes continuously. Infrastructure or uncertain
usage errors stop the batch and remain visible. It never redeems usage-reset
credits automatically or substitutes another model.

### Pre-action timeout recovery

The expanded sweep hit a 180-second provider timeout on GPT-5.5's first
Bruno response, before any controller actions or game frames. That attempt
remains archived with unknown usage. One fresh replacement attempt passed.
The original provider, prompt, timeout, save and task limits stay unchanged.

The supervisor now permits exactly one replacement for this specific
pre-action timeout condition. It never retries a gameplay failure or a
second timeout of the same evaluation. Before a replacement, it reserves
the interrupted task's full token ceiling and verifies that recorded usage,
all remaining task ceilings and every interruption reserve fit inside the
original total budget. Reservations are not claimed as measured usage.
The page labels the recorded token total and keeps unreported call usage
visible even after a replacement passes. Other errors still stop for review.

### Cost efficiency reporting

The portal backfills Standard-rate Codex credit estimates from each saved
input, cached-input and output token record. The rate card is versioned as
`codex-standard-2026-10-03`, with its source and rates embedded in JSON exports.
This is a normalized estimate, not an API invoice, subscription charge or
included-plan quota estimate. No model run or saved result is modified.

Cost comparisons require the same completed, replay-verified tasks and repeats
for every model, plus complete usage reconciled against each run's totals.
An interrupted call with unknown usage excludes that task from cost comparisons
for every model. Partial recorded estimates remain visible in attempt details.
Pending costs and unknown model rates are never treated as zero.

Each task has equal weight. Credits per success divides the sum of per-task
mean credits by the sum of per-task success fractions. Failed attempts count
in cost. Zero successes have no finite cost-per-success estimate. Cost coverage
and its corresponding success rate are shown separately from ability coverage.
CSV includes token categories and estimate completeness. JSON also includes
cost rankings, eligible task IDs and the frozen rate card. Current prices apply
to all saved runs for a consistent comparison, not historical billing.
