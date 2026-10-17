# Planning diagnosis and contract repair

Version red-v0.29-experimental changes plan validation and the gameplay prompt,
with harness codex-app-server-gameplay-v029 and package 0.20.1. The observation
allowlist stays player-information-v028. No new game facts, hints, navigation,
automatic decisions or memory capacity changes are introduced.

## Observed failure

Intentionally pause starter-plan-v028-luna-10m-01 at 61 decisions and 516431
reported input plus output tokens, with no starter obtained. Preserve the frozen
runtime and original trial files. Replay verifies all 300 controller actions
and 9174 frames. Exact model payload and screenshot delivery verifies all 61
calls. The supervisor's finished-only assertion is retained as an audit artifact.
The live status is annotated as an operator pause, not an exhausted-budget result.

The model submitted 46 non-null plan objects containing 19 distinct goal strings.
These are updates, not 46 distinct strategies. Eighteen revision reasons were the
literal string null. One was :null. At decision 33, Luna's own output identifies
the rival and states Oak is absent, then proposes triggering starter selection
through a ball. The clue was present. Information delivery alone is not success.
Fresh conversation mode remains in use, with agent notes and observed history
carried into each decision. This is not the same interaction pattern as an agent
retaining its conversation. Its causal effect on this failure is not isolated.

## Contract repair

Reject empty, punctuation-only and placeholder plan fields such as null, none
and n/a. Require actual JSON null to retain the current plan. Normalize surrounding
whitespace. An otherwise identical plan with a rewritten revision reason is a
no-op, preserving its original set_at_decision and revision history. Real changes
to evidence, goal or completion conditions remain explicit revisions.

This validates a structural contract. It does not prove that revision evidence
is true or that a strategy is good. Do not freeze a bad goal or supply the answer
under the name of plan enforcement. Invalid responses use the existing error
feedback and retry limit. No pending trial is resumed with the changed runtime.

## Read-only diagnostic

Use recorded model-visible snapshots from decisions 33 and 61. Run Luna at medium
effort in isolated subscription sessions with no external tools. Each snapshot
receives one ordinary action request and one progress-review request under the
original gameplay instructions. The review asks for observed facts, unsupported
assumptions, failed experiments, next subgoal and success evidence. It supplies
no prerequisite, route or solution. No response is executed in the emulator.

After inspecting those four responses, make two exploratory follow-up requests
using the same review question and snapshots. Remove redundant raw controller
feedback and legacy partial dialogue and movement fields. Keep all 50 semantic
decision records. Resolve existing encounter references to their exact observed
text inline. No new fact is added. This follow-up is exploratory, not a
preregistered comparison. All six calls together use 56676 reported tokens,
including cached input. Reserve 20000 tokens before each call under an 80000
allowance. As with the benchmark, this is checked between calls, not a backend
hard output limit. Keep exact private requests, responses and client session IDs.

Both ordinary action requests return to the starter balls. The first review
recognizes unsupported assumptions but gives no concrete alternative beyond
trying a distinct interaction. The later review still returns to the display
and confuses dialogue associations. Inline dialogue improves some descriptions
but both follow-ups still propose approaching the balls. One local navigation
suggestion changes. None of these responses establishes a successful new strategy.

These six diagnostic responses are not gameplay trials, a success-rate estimate,
or proof that Luna cannot solve the task. Do not count them as benchmark wins or
failures. Neither generic reflection nor this evidence reformatting warrants a
new long campaign based on these results. Keep the presentation experiment out
of the production observation policy.

## Next causal comparison

The next isolated experiment should compare retained conversation against fresh
sessions from the same checkpoint, with identical model, effort, observations,
actions and total reported-token allowance. First verify that retained turns and
metered compaction actually reach the model. Measure demonstrated game progress,
repeated interactions and token use, not presence of plan fields. Do not change
memory size, add walkthrough hints or change models in that comparison. A
persistent conversation remains a hypothesis, not a promised solution.
