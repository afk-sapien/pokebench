# Five-category Gen 1 benchmark plan

Across both benchmarks, the catalog has **49 primary tasks and one inventory variant** across five
categories: 12 navigation, 16 battle, 10 operations plus one variant, 10 quests and one campaign. Every task case has a checked starting save and a runtime
evaluator. The twelve [milestone tasks](#milestone-tasks) ship in the local fixture pack.
Difficulty remains provisional until model trials.
Historical results and the old fixture set remain available.

**PokeBench** contains the 48 focused tasks and one inventory variant in four
categories, 51 runs over 49 tasks under Short suite version `red-v0.64-harder-short`.
A Short score belongs to its suite version. Runs made on `red-v0.63-short-guard`, 46 runs
over 44 tasks and the set behind the Haiku, Terra and Sonnet runs, stay valid for that set
and are ranked separately. See [Short suite versions](#short-suite-versions). Its score averages them equally: navigation, battle, operations and
quests. The 10 preparation tasks left Short on 14 November 2026. Their stored
attempts stay in the run data, but no report or page reads them. **PokeBench Long** contains only the continuous campaign. They use
separate batches, token ceilings and reports. See [track commands](../history/benchmark-tracks-v053.md).

Navigation tests spatial problems. Quests test NPC instructions and meaningful
prerequisite sequences. Travel within a quest is incidental, not another score.
The short Pokemon Center walk and arbitrary department-store floor checklist are
retired from new batches. So are the two Pikachu capture quests, because a wild
encounter of about 5% decided the search. The full-bag bicycle exchange is an easy manual inventory
variant of the checklist, not a separate quest. Variants share the parent task's
weight in category averages.

The Bicycle quest requires the free Fan Club voucher and its exchange. It is not
a money-grinding challenge. Reviewer explanations appear in the portal without
being added to agent prompts. The machine key `objectives` remains for compatible
links and records. The portal calls this category Quests, and the CLI also accepts
`--category quests`.

| Category | Skill | Controls | Scoring approach |
| --- | --- | --- | --- |
| [Navigation](navigation.md) | Choose routes and understand space | Assisted mechanics, no route planner | Arrive at the declared destination with task constraints |
| [Battle](battle.md) | Make tactical choices during fights | Move, item and switching shortcuts | Battle outcome and explicit survival or resource constraints |
| [Operations](operations.md) | Carry out exact interface instructions | Manual buttons, waits and inspection | Correct targets, quantities and final state |
| [Quests](objectives.md) | Follow NPC instructions and quest dependencies | Assisted mechanics | Verified objective completion |
| [Campaign](campaign.md) | Combine skills over a sustained objective | Assisted mechanics and shared memory rules | Completion plus declared progress milestones |

## Milestone tasks

Twelve Short tasks are longer, such as a whole dungeon or a full League run. Each sits in
its usual category and weighs the same as any other task in that category's average.

Each one lists ordered milestones in its catalog entry, for example the floors of a
dungeon and its exit. A milestone is a fixed check on game memory: map, position, event
flags, bag items, badges, story flags and League wins. A run earns one point for each
milestone, in order, and each one must hold on two different frames. The task score is the
share of milestones reached, from 0 to 1. A run that blacks out or reaches its decision cap
keeps the points it already earned.

The model sees only the task goal, the same screen and the same text it sees in every other
task. It never sees the milestones, their checks or a running score. A start state that
already meets a milestone is refused.

Each milestone task has a checked start state and a scripted reference run that reaches
every milestone. Its decision cap is about five times the reference, and its token budget
is 15,000 tokens per allowed decision. The seven tasks below joined Short with
`red-v0.62-milestone-short`.

| Task | Category | Start | Milestones | Reference decisions | Cap |
| --- | --- | --- | --- | --- | --- |
| [Cross all of Victory Road](navigation.md#cross-all-of-victory-road) | Navigation | 1F entrance, every boulder switch unsolved | 6 | 236 | 1,200 |
| [Reach Articuno in Seafoam Islands](navigation.md#reach-articuno-in-seafoam-islands) | Navigation | 1F west entrance, no boulder in any hole | 6 | 83 | 420 |
| [Reach Giovanni in Silph Co.](navigation.md#reach-giovanni-in-silph-co) | Navigation | 1F front door, every Card Key door locked, no Card Key | 5 | 76 | 380 |
| [Travel from Pewter City to Lavender Town](navigation.md#travel-from-pewter-city-to-lavender-town) | Navigation | Pewter Pokemon Center, early story, Cut and Flash party | 6 | 221 | 1,100 |
| [Defeat the Elite Four and the Champion with no items](battle.md#defeat-the-elite-four-and-the-champion-with-no-items) | Battle | Lorelei's room, empty bag, six level 56 Pokemon | 5 | 100 | 500 |
| [Cross Mt. Moon to Cerulean City with an underleveled party](battle.md#cross-mt-moon-to-cerulean-city-with-an-underleveled-party) | Battle | Mt. Moon Pokemon Center, two level 5 Pokemon, 2 Potions, wild encounters on | 4 | 109 | 550 |
| [Find the Secret Key in the Pokemon Mansion and win the Volcano Badge](objectives.md#find-the-secret-key-in-the-pokemon-mansion-and-win-the-volcano-badge) | Quests | Cinnabar Pokemon Center, Mansion switch off, gym locked, two Pokemon near level 47 | 5 | 202 | 1,000 |

Published rows keep the harness version and task set they were run on. Each row averages
only the tasks its version ran, so these tasks count only on rows run on a version that
includes them.

`scripts/reference_milestone_tasks.py` plays each task with the same assisted commands a
model gets, one decision per command. It makes no model calls. It replays the native
inputs through the catalog runner and writes the reference proof next to the private start.

```sh
uv run python scripts/reference_milestone_tasks.py --rom ROM --game-data GAME_DATA \
  --fixtures FIXTURES --output OUTPUT --tasks navigation-victory-road navigation-seafoam-islands
```

## Harder Short tasks

Five harder milestone tasks joined Short with `red-v0.64-harder-short`. They sit in the
released navigation, battle and quests catalogs, `run --suite short` plans them, and their
runs record the track `pokebench`. `setup` and `run --suite short` add their starts to an
older `data/fixtures` folder from the hash-checked pack, so no separate step is needed.
`tests/test_harder_tasks.py` checks their pins, caps, stop rules and shipped starts.

Each catalog entry pins its start and its scripted reference: the start state digest, the
digest and count of the reference's native inputs, the replayed frames and the decisions.
The decision cap is five times the reference decisions, rounded half up to two significant
figures. The token budget is 15,000 tokens per allowed decision. No model has run these
tasks yet.

| Task | Category | Start | Milestones | Reference decisions | Cap |
| --- | --- | --- | --- | --- | --- |
| Open both trash can locks in the Vermilion Gym and reach Lt. Surge | Navigation | Gym door, both locks shut, trainers beaten, one level 25 Wartortle | 3 | 70 | 350 |
| Reach the Safari Zone secret house and get HM03 in one entry | Navigation | Center area entrance, 500 steps, 200 money, one level 50 Nidoking | 3 | 73 | 370 |
| Fetch a drink for the thirsty guard and enter Saffron City | Quests | Route 7 gate, no drink given, empty bag and PC, 500 money, one level 40 Jolteon | 3 | 68 | 340 |
| Defeat the Elite Four and the Champion with no items and no faint | Battle | Lorelei's room, empty bag, five level 55 Pokemon | 5 | 109 | 550 |
| Defeat the Champion's six with three Pokemon, no items and no faint | Battle | First Champion battle menu, empty bag, three level 60 Pokemon | 2 | 22 | 110 |

Two opt-in fields of the milestone runtime stop a run early, and only these tasks set
them. With `no_faint` a run stops the moment any party member faints, not only on a
blackout. Both harder battle tasks set it. `fail_on` lists checks, in the same form as a
milestone's, that stop the run when one holds on two different frames. The Safari Zone task
sets it for the Safari Zone gate, because the player cannot pay for a second entry. A stopped
run keeps the milestones it already earned, and a start that already breaks a rule is
refused. Adding these fields changes the harness source hash.

The released Elite Four task is unchanged. The no-faint version starts weaker, with five
level 55 Pokemon and no Snorlax against six level 56 Pokemon in the released start. On the
released start the greedy reference wins with five faints. The harder reference adds one
rule to it. When the opponent's strongest move could knock out the active Pokemon, it heals
with Recover if it moves first, or else switches to the party member that best takes the
hit. On the new start it wins with no faint, healing twice and switching 11 times. With
the same party at levels 50 to 54 it loses.

`scripts/prepare_harder_fixtures.py` is the maintainer step that built the starts, and two
builds give the same state digests. `scripts/reference_harder_tasks.py` plays each reference
with the assisted commands a model gets, one decision per command, and writes the proof next
to the start. Neither makes model calls. Users never run them, because the starts and proofs
ship in the fixture pack.

```sh
uv run python scripts/prepare_harder_fixtures.py --root DATA --archive STATES --rom ROM \
  --game-data GAME_DATA --output FIXTURES
uv run python scripts/reference_harder_tasks.py --rom ROM --game-data GAME_DATA \
  --fixtures FIXTURES --output OUTPUT --tasks battle-elite-four-no-items-no-faint
```

## Short suite versions

[short_suites.json](../../src/pokeagent_bench/short_suites.json) records every Short suite
version with its benchmark name, run count, task count and each run's task, variant,
`evaluation_spec_sha256` and `fixture_sha256`. A Short score belongs to the version whose
runs it holds exactly. `tests/test_suite_versions.py` checks that the current catalog matches
the current entry.

| Version | Runs | Tasks | Runs made on it |
| --- | --- | --- | --- |
| `red-v0.63-short-guard` | 46 | 44 | Haiku, Terra and Sonnet |
| `red-v0.64-harder-short` | 51 | 49 | None yet |

`red-v0.64-harder-short` keeps all 46 runs of `red-v0.63-short-guard` with the same digests
and adds the five harder tasks. Runs on the older set stay valid for that set and are ranked
separately. Release `v0.38.0` is the first to run it. A finished older Short folder is topped
up in place: its 46 runs are kept and only the five new runs start. The plan, the run summary, the bundle and the verified report each name the suite
version with its run count.

## Inspect the catalog

```sh
uv run pokebench catalog
uv run pokebench catalog --category operations
uv run pokebench catalog --fixtures /private/fixture-root
```

The catalog includes the start, success and failure conditions, difficulty target,
variant ideas, provisional token ceiling, reusable existing task and missing work
for each eval. Inspection makes no model calls. A source fixture link is a reuse
candidate, not a claim that it satisfies the new scenario or grading contract.
An existing objective is included only where its implemented predicate matches the
proposed outcome. Other entries explicitly need a new grader.

Current runtime support remains Pokemon Red. Blue is an intended extension and
needs its own ROM, observation, grading and fixture checks before results are
presented as cross-version evidence. The same scenario in two versions is a
transfer test, not automatically two independent skills.

## Difficulty and rollout

Easy, medium, hard and stretch are design targets. Use inexpensive reference
controllers and a small model pilot to find tasks that separate model tiers.
Some harder candidates should challenge the strongest models, but avoid tuning
all scenarios specifically against one model's known failures. Shared starting
conditions improve comparisons without eliminating battle randomness.

Start with a few representative focused evals and a bounded campaign pilot. Prefer reusable checkpoints
where the new success condition actually matches the existing one. Promote more
candidates after validating their starting state, scoring and controller behavior.
Do not rerun the historical collection merely because this plan adds categories.
No new model sweep is started by adding these specifications.

## Results

Keep one benchmark page. Use category filters rather than separate suite menus.
Show category success, coverage, tokens and replay links. Keep operational
competence and full-game campaign progress visible separately from focused
gameplay scores. Easy interface tests and correlated campaign milestones must
not inflate strategic ability. Within categories, variants of
a task share its weight rather than multiplying its influence. Missing results
remain pending. Existing results stay visible with their recorded conditions.

## Visual catalog

Open `catalog.html` from the results page's Task catalog link to browse all five
categories, search the 45 specifications and expand their goals, controls and
remaining work. Category and task URLs can be bookmarked. Planned specifications
are not reported as completed evaluations or assigned historical scores.

New website exports include the catalog automatically. To refresh an existing
local results export without regenerating its results or replays:

```sh
uv run python scripts/export_catalog.py --output /path/to/results-export
```

This command updates the catalog, adds its navigation link and refreshes hashes
for those files in the existing export manifest. It does not publish the site.

## Concrete scenario revision 2

The first revision described several skill families instead of actual scenarios.
Revision 2 names the Pokemon, opponents, locations, inventory, intended starting
state and required outcome. Each task includes `agent_goal`, `scenario_details`
and `open_questions`. The portal shows these as the planned instruction, concrete
setup and remaining checks.

A new species or different gym is a different scenario, not an unnamed timing
variant. Task IDs remain stable for this planning revision. Existing scored
results are not relabeled, invalidated or merged into the revised drafts.
The running gameplay protocol has not changed and no new model trials were
started. Native map/script facts checked from upstream sources are linked in the
category documents. Proposed parties and budgets still need save validation and
calibration before claims about difficulty or readiness.

## Revision 3: remove duplicate campaign launches

The catalog now contains 8 navigation, 12 battle, 10 operations, 10 preparation,
10 objectives and 1 full-game campaign specifications. Category counts are not
quotas. Navigation measures reaching a destination or solving a spatial puzzle.
Objectives measure a quest, prerequisite or capture outcome. Travel within a quest
is incidental and is not awarded again as a separate navigation pass.

The full-game campaign is one evolving game per attempt with 50 weighted progress markers. See [the campaign scoring plan](campaign.md)
for the exact quests, towns, badges, League victories and capped collection bonuses.
Record cumulative tokens, decisions and elapsed time at first achievement. Badges
may be earned in different orders. Keep the actual chronology. Blackouts may be
recovered from through normal gameplay while budget remains.

Those 50 observations are correlated progress within one attempt. They are not
50 independent evaluation samples. Report full completion, a milestone checklist
and existing campaign points separately from focused checkpoint success rates.
Do not infer a checkpoint task pass from campaign progress with a different team.
Optional quests can appear in the timeline without becoming extra ranked tasks.

The starter-to-parcel, starter-to-Brock and badge-chain campaign launches have
been folded into campaign progress. The fixed-team League starts move to Battle,
and Rocket Hideout and Abra-to-Misty move to Objectives. Redundant opening travel
and the second Snorlax objective are removed from this proposed catalog. The
forced context-reset parcel test is retained only as an internal diagnostic draft.
Original planning entries are preserved in `retired-v3.json`. Historical results
and runnable suites are unchanged. No new model runs are launched by this change.

The runtime already records confirmed badge, Elite Four and Champion awards.
Starter/parcel checklist integration and per-milestone token attribution remain
implementation work, as recorded in the campaign entry. This is a revised plan,
not a claim that a new campaign result renderer has already been implemented.

## Revision 4: holistic campaign reporting

The campaign now specifies 50 milestones and a proposed 1000-point score. Badges,
Elite Four victories and Champion completion supply 800 points. Story progress
supplies 100, town/League access 50 and capped collection/development bonuses 50.
Champion completion stays the primary outcome. Purchases, raw level/stat totals,
repeat encounters and resource spending do not directly award points.

The same attempt also produces a separate profile of party readiness, move
coverage, captures, evolutions, battles, blackouts, transactions and efficiency.
Record party snapshots at common milestones so comparisons are made at comparable
progress. Party stat totals are descriptive, not a calibrated battle-power metric.
The catalog declares collection and reporting work still needed. No historical
scores or running trials are changed by this plan, and no model runs are launched.


## Cleanup revision v0.52

The earlier count and design notes below the current overview describe previous
revisions. `archive-v051.json` preserves the definitions before this cleanup.
To copy existing private saves into the new revision without changing old artifacts:

```sh
uv run python scripts/rebind_catalog_fixtures.py --source /path/to/catalog-v1 --output /path/to/catalog-v2
uv run pokebench catalog-validate --fixtures /path/to/catalog-v2 --rom /path/to/pokered.gb
```

Rebinding never changes the emulator state. A changed task definition does not
inherit a reference proof recorded under a different specification hash.

## Preparation leaves Short, 14 November 2026

The 10 preparation tasks, their fixed-controller assessment and the preparation
column are gone. Stored preparation attempts stay on disk. Reports, the analysis
page and the site skip them. Ranked scores and rank order did not change, because
preparation was never part of the ranked score. Each published model now counts
39 planned starts instead of 49.

## The Poke Flute milestone task is retired, 14 November 2026

`objectives-poke-flute` chained the Rocket Hideout and the Pokemon Tower rescue. Both
halves are already Short quests, `objectives-quest-trainer` and
`objectives-prerequisite-chain`, so it scored the same skills twice. Its cap of 2,000
decisions and 30M tokens was also the size of a whole Long run. No model ran it. Its
definition, start recipe and reference script stay for history. Short now has seven
milestone tasks and nine quests.
