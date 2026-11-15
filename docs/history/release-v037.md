# Milestone Short red-v0.62

This tag freezes the harness that `main` grew after `v0.36.0`. It is released
as package 0.37.0, git tag `v0.37.0`, under the harness name
`red-v0.62-milestone-short`. No model was called to build or check it. Every new
start was checked by a scripted reference that plays the task to its end, and
the recorded inputs were replayed.

## Short starts all 44 tasks

Short at `v0.36.0` had 47 tasks. After that tag the 10 preparation tasks left
Short and the seven milestone tasks joined it, which gives 44. The v0.36.0
fixture pack had no fixture for the seven, so a fresh setup from `main` held
them and Short started 37 tasks. This pack carries a checked start and a
replayed reference proof for each, so Short starts all 44.

| Task | Reference decisions | Score | Replay |
| --- | ---: | ---: | --- |
| `navigation-victory-road` | 236 | 6 | verified |
| `navigation-seafoam-islands` | 83 | 6 | verified |
| `navigation-silph-co` | 76 | 5 | verified |
| `navigation-pewter-to-lavender` | 221 | 6 | verified |
| `battle-elite-four-no-items` | 100 | 5 | verified |
| `battle-mt-moon-underleveled` | 109 | 4 | verified |
| `objectives-cinnabar-gym` | 202 | 5 | verified |

The references are the command scripts in `scripts/reference_milestone_tasks.py`.
They use only the commands a model has. They prove that each task can be
finished from its start, and they are never leaderboard results.

## Navigation starts carry their Max Repels

The task text of `navigation-warp-puzzle`, `navigation-spinning-floors` and
`navigation-boulder-puzzle` promises 20 Max Repels, item 57. Their starts in the
v0.36.0 pack held item 84 instead, the B2F elevator label. Commit `a2dc0a3`
fixed the recipe and this pack ships the fixed starts. The task specs are
unchanged, so only the start state hash differs. Runs before this tag started
these three tasks with the elevator label in the bag.

## Long is scored by the v2 milestone list

The campaign spec changed when Long moved to the 25 dungeon and route
milestones, so a fresh setup held `campaign-full-game` with "Fixture
specification changed". Its start state is unchanged. The fixture was rebound to
the current spec with `scripts/rebind_catalog_fixtures.py`, which records the
earlier spec hash next to the new one.

## The pack

The pack holds 438 files and 88 start states, up from 398 files and 81 states.
The seven new tasks add six files each. The two preparation binding files are
no longer packed, because the preparation tasks left Short before this tag.
Setup on a clean folder reports 45 tasks ready and none held, which are the 44
Short tasks and the Long campaign. A Short plan has 46 runs over 44 tasks,
because `battle-uncertain-opponent-lineup` has three starts.

## What the label covers

Besides the fixtures, the tag collects the changes merged after `v0.36.0` that
alter what a model sees or how a run ends. The text map now shows surfable
water, cave holes, Cut trees, the Victory Road floor switch, the Silph Co Card
Key doors, the Rocket Hideout doors and the Pokemon Mansion and Cinnabar Gym
gates, switches and quiz machines. It hides the terrain in a dark cave. Long runs stop after 10M tokens
without a milestone, and each extension chunk has its own allowance.

## Accepted releases

The v0.37.0 entry is added to
[accepted_harness.json](../../src/pokeagent_bench/accepted_harness.json) after
the v0.36.0 entry, which stays. A v0.36.0 bundle is verified on the v0.36.0
checkout, because its Short suite and three of its starts differ from this
one. Existing leaderboard rows keep the harness label they ran on.
