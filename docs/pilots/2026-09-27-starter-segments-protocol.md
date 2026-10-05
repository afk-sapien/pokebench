# Starter segment protocol

Scenario protocol starter-segments-v014. The user requested starting downstairs
or outside. Create both private checkpoints from the previously verified
starter-v010 controller reference, then run the outside scenario first.
Do not treat this as completion of the original start-at-home task.

## Fixture construction

Use scripts/prepare_starter_segments.py. Replay the reference from the original
save and capture the first recorded action boundary on the ground floor and
outside. No game-memory writes, invented state, automatic route planner or
unrecorded setup inputs are used. Keep the paired screenshot and save from the
same frame, with zero added setup frames. Verify every reference prefix image,
restore each checkpoint and execute its remaining reference suffix. Require
identical suffix screenshots and successful evaluator completion. Reject an
initial state that already has a starter. Keep raw fixtures and reference
artifacts private. Export hashes and counts only.

Both objectives say: Obtain your first starter Pokemon from Professor Oak.
Find your own way. Finish the acquisition dialogue and decline a nickname.
The earlier phrase about beginning at home is removed because it is no longer
true for the outside checkpoint. Do not provide route hints or object labels.

## Live outside batch

Run gpt-5.6-luna, gpt-5.6-terra and gpt-5.6-sol on the same outside checkpoint.
Retain the frozen v0.11 runtime, medium effort, visual track, original 3x current
screenshot, simple response contract, continuous conversation and 24,000-token
metered summary threshold. No observation-first treatment is promoted.

Each model has 250,000 reported input plus output tokens, 100 model calls,
300 actions, two actions per decision, 600 frames per action, 120,000 total
frames and 1,800 seconds. Reserve before calls. The combined allowance is
750,000 reported tokens, with the existing possible final-response overrun.
Stop on completion or a run limit. Do not retry, substitute models or increase
budgets automatically. Preserve unknown usage on failures. Other capped runs
may finish independently.

Compare progress, starter receipt, completion, decisions, actions and token
usage. Verify full controller replay and recorded image evidence before
reporting. Distinguish new-checkpoint success from original-checkpoint success.
A single trial per model does not prove a causal effect or model ranking.
The downstairs fixture is prepared and reference-verified only in this batch.
No additional downstairs model batch is launched automatically.
