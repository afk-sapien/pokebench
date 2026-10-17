# Six-category Gen 1 benchmark plan

Across both benchmarks, the catalog has **48 primary tasks and one inventory variant** across six
categories: 6 navigation, 12 battle, 10 operations plus one variant, 10 preparation,
9 quests and one campaign. All 49 task cases have checked starting saves and
runtime evaluators in the local `data/catalog-v2` fixture set. Difficulty remains
provisional until model trials. Historical results and the old fixture set remain
available.

**PokeBench** contains the 47 focused tasks and one inventory variant in five
categories. **PokeBench Long** contains only the continuous campaign. They use
separate batches, token ceilings and reports. See [track commands](../history/benchmark-tracks-v053.md).

Navigation tests spatial problems. Quests test NPC instructions and meaningful
prerequisite sequences. Travel within a quest is incidental, not another score.
The short Pokemon Center walk and arbitrary department-store floor checklist are
retired from new batches. The full-bag bicycle exchange is an easy manual inventory
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
| [Preparation](preparation.md) | Choose a useful team and allocate resources | Preparation choices, then freeze the submission | Automated evaluator battle outcomes |
| [Quests](objectives.md) | Follow NPC instructions and quest dependencies | Assisted mechanics | Verified objective completion |
| [Campaign](campaign.md) | Combine skills over a sustained objective | Assisted mechanics and shared memory rules | Completion plus declared progress milestones |

## Inspect the catalog

```sh
uv run pokebench catalog
uv run pokebench catalog --category preparation
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

## Preparation is evaluated separately from battle execution

The evaluated model makes preparation choices and ends its submission. Copies of
that configuration are then tested by a fixed automated battle evaluator. The
model is not asked to play those grading battles. Use the same controller,
search allowance, opponent conditions and starting variants for every submission.
No model-generated battle policy is accepted as part of the preparation answer.

The controller is a strong reference policy, not a claimed optimal player. Check
that it supports the strategies the task permits, including status, setup and
switching. Otherwise it can incorrectly penalize a good preparation. Report win
rate and per-condition performance. Calibrate any pass threshold against competent
and weak reference preparations before comparing model scores. Near-threshold
estimates may need more trials under the same sampling rule for every model.
A frozen team alone is not proof that a team is legal or that its battle results
are attributable to the submitted preparation. Validate the allowed roster,
resources, moves and unchanged opponent conditions during fixture construction.

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

Open `catalog.html` from the results page's Task catalog link to browse all six
categories, search the 51 specifications and expand their goals, controls and
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
