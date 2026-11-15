# Short milestone guard, v0.37.1

Since v0.37.1 each Short task stops after two thirds of its own token cap without a new milestone. The stop reason is `milestone_token_budget`, the guard Long already uses at 10M tokens. A pass or fail task has no milestone before it passes, so it stops at two thirds of its cap. A milestone task counts from the token stamp of its latest milestone, and the milestones it already earned keep their points.

The guard is a per-task run limit in the suite plan, so `verify` requires it on every Short run. Short milestone awards now record the decision and the token count, which is what the guard reads. Replay compares only the id, points and frame of each award, so older runs still replay.

## Why two thirds

No model was called. Stored runs were replayed against each guard as a token count. A failure that used more than the guard saves the tokens past it. A success that used more than the guard counts as lost.

| Stored runs | Runs | Tokens | Half saves | Half loses | Two thirds saves | Two thirds loses |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| v036 Short, Haiku 5.5 | 39 | 59.9M | 14.6M | 0 | 9.0M | 0 |
| v036 Short, Sonnet 5.5 | 39 | 46.9M | 7.5M | 0 | 3.0M | 0 |
| Published Short, 8 models | 308 | 310.5M | 8.4M | 1 | 1.2M | 0 |

These are the pass or fail tasks of the current Short suite. Retired tasks and runs with a harness fault are left out.

At half the cap, one published success is lost. Fable 5.1 passed `objectives-infeasible-plan-alternate` at 0.60 of its cap. The largest share used by any v036 success was 0.35.

## Milestone tasks

The seven milestone tasks have no stored Short model runs. Their gaps come from the 17 Long runs, read from the v2 milestone stamps where a campaign passes through the same caves and buildings. A Short milestone that Long does not stamp is merged into the next gap, so these gaps run long and the losses are an upper bound. A campaign that moved on without the next stamp is taken to stall until a cap at its own tokens per decision, so the savings are rough.

| Task | Long runs | Half saves | Half loses | Two thirds saves | Two thirds loses |
| --- | ---: | ---: | ---: | ---: | ---: |
| `battle-mt-moon-underleveled` | 14 | 22.2M | 2 | 10.9M | 0 |
| `navigation-pewter-to-lavender` | 14 | 38.0M | 0 | 21.5M | 0 |
| `objectives-cinnabar-gym` | 2 | 0 | 0 | 0 | 0 |
| `navigation-silph-co` | 2 | 0 | 0 | 0 | 0 |
| `navigation-victory-road` | 1 | 0 | 0 | 0 | 0 |
| `battle-elite-four-no-items` | 1 | 0 | 0 | 0 | 0 |

`navigation-seafoam-islands` is on no stored Long route, so it has no data. The longest stretch that still ended in a milestone within the task caps was Fable 5.1 from the Mt. Moon entrance to its second basement, at 0.646 of the Mt. Moon cap. Two thirds keeps it.

The guard is checked after each decision, so a run can pass it by at most one decision's tokens.
