# PokeAgent Bench suite v1 proposal

Status: future expansion proposal, 2026-09-29. The active scope is now the five-task basic suite described in ../basic-suite.md. This document does not launch trials or
claim that the proposed suite commands, fixtures or graders are implemented.

## Decision

Ship one installable benchmark package with 12 independent checkpoint tasks and
3 separately scored endurance tasks. The default leaderboard uses the 12 checkpoint
tasks. Campaigns measure sustained performance without dominating the cost or
score of the checkpoint suite. Difficulty labels and budgets below are provisional.
Calibrate them once on development fixtures, then freeze them before scored runs.

Use the current assisted gameplay interface as the primary track: screenshots,
local observed terrain and objects, party, moves, bag, storage inspection, exact
encountered dialogue, agent notes and bounded retained conversations. Keep visual-only
results in a separate track. Rank a model with its harness, prompt, observation
policy, reasoning setting and budget, not the model name alone.

## Inspiration

LatchBio scBench pairs data snapshots with natural-language tasks and deterministic
graders. Its published results distinguish model and harness and break performance
down by task category. We can apply this structure to saved games, task prompts
and verified game-state outcomes.
Source: https://github.com/latchbio/scbench

LatchBio BioSecBench-Surveillance runs repeated attempts and averages within an
evaluation before aggregating evaluations, rather than treating correlated repeats
as separate problems. Adopt task-level aggregation and explicit uncertainty.
Its refusal exclusions are not appropriate for our gameplay suite. Refusing or
abandoning a valid gameplay task counts as failure here.
Source: https://github.com/latchbio/biosecbench-surveillance/blob/main/METHODS.md

LatchBio also evaluates long-horizon workflows separately. Use a separate endurance
report for long Pokemon campaigns.
Source: https://blog.latch.bio/p/verifiable-benchmarking-of-long-horizon

## The proposed 15 tasks

M means one million reported input plus output tokens, including cached input.
Caps are initial calibration candidates, not forecasts of required usage.

| ID | Difficulty | Task and starting position | Verified completion | Main capability | Candidate cap |
| --- | --- | --- | --- | --- | ---: |
| 01 | Easy | Obtain a starter from the existing outside-lab checkpoint, before Oak's introduction | First starter acquired and nickname prompt declined | Quest prerequisites and dialogue | 1M |
| 02 | Easy | Win a wild battle from its command menu, with a healthy suitable party | Original opponent defeated, experience earned and battle exited alive | Basic combat | 0.25M |
| 03 | Easy | Catch a first wild Pokemon, starting near grass with a starter and limited balls | New capture during this attempt and nickname prompt resolved | Capture strategy and inventory | 0.5M |
| 04 | Easy | Heal a damaged party, starting outside the nearby Pokemon Center | Same party restored to full HP and PP with statuses cleared, without a blackout | Navigation and interaction | 0.5M |
| 05 | Medium | Collect Oak's Parcel and return it, starting after starter acquisition | Pickup observed, delivery confirmed, parcel removed and Pokedex received | Roundtrip planning | 1.5M |
| 06 | Medium | Cross Viridian Forest from its south entrance with a prepared party | Reach the north exit alive | Navigation and incidental combat | 1M |
| 07 | Medium | Defeat Brock from the first battle menu with a healthy, adequate team | New Boulder Badge and verified Brock victory | Battle decisions | 0.5M |
| 08 | Medium | Cross Mt. Moon from the western entrance with fixed supplies | Reach its eastern exit alive | Multi-floor exploration and endurance | 1.5M |
| 09 | Hard | Prepare for Brock from Pewter City with an underleveled, unfavorable party | New Boulder Badge, with preparation through normal gameplay allowed | Team building and preparation | 2M |
| 10 | Hard | Recover from low HP and PP at a verified reachable cave checkpoint | Reach the designated Pokemon Center and restore the same party without a blackout | Resource management and recovery | 1M |
| 11 | Hard | Resolve Silph Co. from the building entrance with a prepared team and required access | Defeat its Giovanni encounter and receive the Master Ball | Multi-step quest and maze planning | 2M |
| 12 | Hard | Beat the Elite Four and Champion from League entry with a fixed competitive party and bag | New Hall of Fame registration after the required victories in one attempt | Sustained combat and item allocation | 3M |
| 13 | Endurance | New game to Boulder Badge, beginning at a standardized post-name bedroom save | Newly earn the first badge | Early-game skill integration | 5M |
| 14 | Endurance | New game to Cascade Badge from the same bedroom start | Newly earn both first and second badges | Longer exploration and team development | 10M |
| 15 | Endurance | New game to Champion from the same bedroom start | All required badge progress and new Hall of Fame registration | Full campaign and long-term memory | 30M |

All party compositions, levels, moves, resources and allowed travel must be fixed
in each fixture manifest. Task 07 needs a new healthy fixture. The existing
brock-battle-v015 save starts with a wounded lead and must not silently stand in
for this baseline. Task 09 must have a controller-only reference proving that
preparation is feasible. Task 10 is a recoverable problem, not an alleged soft lock.
Task 12 needs full reference validation. league-recovery-unverified is not ready
for scored inclusion. Endurance starts exclude naming menus, and reports must say so.

The default rule is to keep species names. Include every task-specific restriction
in the agent's task description, such as no blackouts. Never grade an undisclosed
restriction. Preparation and tactical choices remain the model's responsibility.

## Fixture construction and acceptance

Use PokeSim as an offline checkpoint generator in an isolated instance, or extract
checkpoints from recorded valid controller traces. Do not change the running
PokeSim project or its saves. Capture exact states using controller inputs only.
No RAM edits, injected items, altered party statistics or benchmark-side teleports.

For every fixture, require:

1. Pinned ROM hash, emulator, Core, observation bundle and starting-state hash.
2. Starting objective not already satisfied, with explicit initial party and bag.
3. A successful reference trajectory whose replay reproduces the outcome.
4. Negative traces that fail correctly, including fleeing instead of winning,
   parcel pickup without return, entering a gym without winning, and a blackout
   instead of successful recovery where prohibited.
5. Grader completion checked at stable game boundaries, with terminal dialogue
   handled consistently. Capture must be distinguished from gifts and withdrawals.
6. Restoration and pause/resume checks that preserve evaluator state and budgets.

The grader may read private event flags, but the model cannot. Grade actual
outcomes rather than requiring one particular route or move sequence. Do not
add reference strategies or hidden quest prerequisites to agent observations.

Use three predeclared fixture variants per task for a later robustness release,
created through normal play with differing teams, resources or encounter state.
Do not pretend a random Python seed reseeds the cartridge. Until variants are
validated, repeat the identical fixed save and label the results accordingly.
Keep development fixtures separate from sealed scored variants. Sealed fixtures
are hidden from benchmark agents, not necessarily secret from package owners.

## Packaging

Extend pokeagent-bench instead of creating another runtime. Keep emulator and
game decoding primitives in PokeSim Core. Keep tasks, private graders, suite
scheduling, budgets, statistical aggregation and report exports in this package.

Proposed package contents:

- Versioned suite manifests defining task order, IDs, fixture hashes, prompts,
  completion rules, stop rules and all token, action, frame and time limits.
- Auditable controller recipes and expected hashes for building checkpoints.
- A fixture validator and isolated local cache.
- A suite scheduler using the existing run, pause/resume and replay mechanisms.
- A result schema, combined HTML report, sanitized JSON/CSV export and paper inputs.

Continue requiring the user's own supported ROM. Distribute code, manifests and
controller recipes without ROMs, images, generated game tables or emulator states.
Build saves locally from the pinned ROM and cache them. A recipe that depends on
an unavailable private save is not sufficient for a reproducible public release.
Late-game generation can take time but happens once, without model tokens.

Proposed CLI, not currently implemented:

```sh
pokeagent suite prepare --suite red-core-v1 --rom /path/to/red.gb
pokeagent suite validate --suite red-core-v1 --rom /path/to/red.gb
pokeagent suite run --suite red-core-v1 --models gpt-5.6-luna gpt-5.6-terra gpt-5.6-sol --repeats 3 --dry-run
pokeagent suite run --suite red-core-v1 --models gpt-5.6-luna gpt-5.6-terra gpt-5.6-sol --repeats 3 --total-token-budget 15000000
pokeagent suite resume --batch batches/example
pokeagent suite report --batch batches/example --output reports/example
```

The illustrative 15M batch allowance is deliberately smaller than a complete
three-model campaign. The scheduler pauses at that allowance and labels coverage
incomplete. It never silently drops remaining tasks or increases budgets.

## Execution protocol and cost control

Freeze the v033 bounded policy for a development pass, including eight-response
segments, a 12000 observed-context threshold, deterministic memory handoffs and
zero paid summaries. Revalidate the full allowlist and inspect payload sizes on
late-game saves before freezing suite v1. Full storage may need pagination.
A change to observation, tools, context policy or limits creates a new comparison
version, not an invisible improvement during evaluation.

Every task gets a fresh game state, notes and model conversation. No state or
strategies leak from another task, model, reference run or repeat. Each model gets
the same task-specific budgets and permitted tools. Register all cells before
starting and interleave model/task order to reduce timing effects. Start with one
concurrent run unless measured capacity supports more. Record queue time separately.

Use one attempt per task as a development pilot, then at least three independent
attempts per task and model for the first descriptive comparison. Three repeats
remain a small sample. Increase replication for close results. A later sealed
variant release must give every model the same variants and repeats.

The candidate core caps sum to 14.75M tokens per model per sweep. Three repeats
allow up to 44.25M per model, or 132.75M across Luna, Terra and Sol. These are maximum
allowances, not predicted consumption. Endurance caps add 45M per model per sweep
and are opt-in. Do not launch these campaigns merely because this plan exists.

Stop immediately on success. Budget exhaustion and invalid model actions count
as task failures. Failed objectives receive no automatic retry with a better
prompt or bigger allowance. Pause on transient provider errors and preserve the
attempt record. Resume the same state only where the existing recovery protocol
can prove continuity. Meter all known usage, including interrupted runs, and mark
unknown usage explicitly. Cap retries under the batch allowance.

Keep infrastructure failures separate from gameplay failures and show both. Do
not publish a complete leaderboard for a configuration with unresolved missing
cells. Prefer a predeclared bounded replacement policy for invalid infrastructure
attempts, retain originals, and report the additional usage.

A room-duration rule is not a general definition of being stuck. Battles, training
and quests can legitimately remain in one area. Use task-specific loop rules
validated on positive reference traces and disclose thresholds. Until validated,
prefer token and frame limits plus non-intervening stall diagnostics.

## Scoring and final presentation

Primary core score: 100 times the mean of the 12 per-task success rates. Average
repeats within a fixture, fixtures within a task, then tasks equally. Do not use
best-of-three as the main score. With four tasks per difficulty tier, tiers also
receive equal weight. Completion is binary. Secondary partial-progress markers
must never turn repeated visits or repeated victories into extra completion credit.

Show pass rates by difficulty and skill, plus a task-by-model heatmap with counts
such as 2/3. Report 95% uncertainty intervals using a documented task-level paired
resampling method for model differences. Preserve paired fixtures across models
and do not treat turns or repeats as independent tasks. Twelve tasks and three
repeats only support limited generalization. Avoid claiming one model is universally
better when intervals are broad or task strengths differ.

Report total tokens consumed across all attempts, input/output/cache breakdowns
when available, and tokens to success. Display successful-run medians only beside
success counts to avoid rewarding a model for quickly failing hard tasks. Also
plot completion versus cumulative token allowance, with incomplete attempts still
in the denominator. Total tokens divided by successes may be useful for deployment
cost, but label it undefined when no run succeeds.

Subscription usage is not a per-run dollar bill. Show metered tokens and available
quota data, with cost unavailable unless genuinely measured. Keep optional API
price estimates separate, dated and explicit about cache treatment. Token counts
are operational limits, not equal compute across tokenizers or model families.

Endurance results remain separate: completion, unique badges, Elite Four victories,
Hall of Fame evidence, tokens, elapsed wall time and emulated time. Preserve existing
campaign milestone scoring only after its real-game detectors are validated.
Do not add campaign points to the core success percentage.

The HTML report should open on the leaderboard and coverage, then allow drilldown
to tasks, repeated attempts, failure reasons and existing decision replays. Add
visible labels for long automatic dialogue/cutscene intervals so boundary snapshots
do not imply teleportation. Any optional continuous replay is reconstructed from
controller logs without model calls. Do not expose reviewer-only evidence to agents.

Export the same frozen sanitized result dataset to the existing paper-scaffold
workflow. Generate tables, figures, suite version, limitations and source hashes
from that dataset so the paper and leaderboard cannot disagree. Preserve raw runs
privately rather than committing them as public paper inputs.

## Implementation order

1. Implement suite manifests, validation, scheduling, batch ceilings and coverage
   reports using the existing starter, wild-battle, parcel and Brock fixtures.
   Mark this a development subset rather than a complete 12-task score.
2. Add capture and healing graders and controller-built fixtures for forest,
   Mt. Moon and weak-party preparation. Audit existing versus proposed constraints.
3. Produce and independently verify Silph Co. and League fixtures. Validate
   negative traces, payload bounds and all late-game detectors before model spending.
4. Calibrate caps and supporting limits on development fixtures, freeze suite v1,
   then run the registered repeated core comparison and generate the paper tables.
5. Run endurance tasks as separately budgeted experiments after core validation.

No paid model trial or implementation change is part of this planning document.
