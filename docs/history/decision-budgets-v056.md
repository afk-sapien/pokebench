# Decision budgets v0.56

PokeBench uses a task-specific decision allowance as its primary limit. One
model response counts as one decision, including inspection, screenshot recall,
invalid commands and waits. A mechanical shortcut counts as one decision even
when it emits several native button inputs. Raw controller inputs and game
frames remain separate telemetry. This is not a tile-count or battle-turn limit.

The focused catalog has 47 primary tasks plus one inventory variant. Champion
roster variants make 50 attempts per model. PokeBench Long is excluded from this
initial pass and its existing limits remain unchanged.

| Category | Decision allowance | Token backstop |
| --- | ---: | ---: |
| Navigation | 200 to 300 | 30,000 per allowed decision |
| Battle | 25 to 400 | 30,000 per allowed decision |
| Manual operations | 40 to 130 | 30,000 per allowed decision |
| Quests | 100 to 650 | 30,000 per allowed decision |
| Preparation | One submitted plan | 50,000 |

These are initial practical allowances, not proven optimal-solution lengths.
The manual healing pilot took 13 to 16 decisions, so its allowance is 40.
Navigation gets room to explore beyond the earlier 13 to 28 decision token caps.
Longer quests and five-battle gauntlets receive more decisions than single fights.
The token allowance is a spending backstop based on the observed roughly 10,000
input-plus-output tokens per decision, with room for variation. It is a total
attempt allowance, not a per-response restriction. Cached inputs count too.

The runner checks both limits before the next model request. An already charged
response can overshoot the token ceiling. Successful completion stops immediately.
The existing `model_call_budget` stop reason means the decision cap was reached.
The agent sees the decision limit, used count and remaining count in each update.
Native input reference checks do not consume model decisions.

Every model gets the same task budgets, current-only screenshot policy, low
reasoning effort where supported, action policy and starting state. Manual menu
tasks keep shortcuts disabled. Preparation uses one frozen plan, followed by
fixed-controller assessments that do not consume model tokens or model decisions.
Preparation continues to report win rate without an uncalibrated pass threshold.

New starts use a separate `catalog-v5` fixture copy. Native states are unchanged.
Old results retain their original allowances. This changes the protocol to
`red-v0.56-decision-budgets` and does not invalidate earlier results.

## Initial pass and practical checks

The current advertised subscription roster is Sol, Terra, Luna, Claude Opus 5.5,
Sonnet 5.5 and Haiku 5.5. This creates 300 attempts. Four workers run concurrently,
at most two per provider. One full-budget attempt on each start checks execution
before that start expands to the remaining models. Those first attempts remain
part of the results. Model losses do not block expansion. Infrastructure errors
hold their task for inspection.

The effective shared backstop is 50 million reported tokens, including cache reads.
The original 200 million proposal was reduced after automatic approval review
rejected the larger recurring allowance. The reduction is recorded separately
in `budget-ceiling.json`, preserving the original plan and all charges.
This is not an expected spend or an instruction to exhaust it. Each in-flight
attempt reserves its full task allowance plus 64,000 tokens. If the shared
backstop cannot fund a full allowance, the task remains pending. No model gets
a smaller task allowance just to fill the remaining aggregate budget.

All 50 focused starts passed native loading, initial observation construction,
packet-size checks and deterministic replay. Twelve available native completion
traces also passed. These checks establish interface readiness, not that all
remaining tasks have been completed by a model.

The first preparation attempts exposed two runtime defects. Core's move
shortcut missed forced turns that completed before four observations, including
Clamp turns consumed inside the blocking menu selector. Core now recognizes the
return from visible turn text or an observed battler change. It does not press
FIGHT again. Tests also retain refusal for ignored input and normal handling of
a delayed move menu.

The fixed preparation assessment controller answered No to the confirmation
asking whether to abandon learning a move. That reopened the same question.
It now confirms abandonment to retain the submitted moves. This policy is
`fixed-battle-v3`. Existing preparation submissions are reassessed offline, with
original outcomes preserved and model charges unchanged. This does not ask a
model for a better preparation or retry a model-played battle loss.

PokeBench uses the local Core `0.6.1.dev1` wheel for the repaired controller.
Its SHA256 is `1f2e6f5d1a4b2bd3020bdc332dcafb306b41eccb63f97ae1fabcc5bc5436fe5d`. Core's source repair is in the
`pokesim-core-gameplay` checkout. The pass archives its original runtime and
records the repaired runtime separately. The local progress page is
`focused-pass-v056.html`, linked from the existing results index.
