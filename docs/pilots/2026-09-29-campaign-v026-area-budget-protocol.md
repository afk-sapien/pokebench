# Terra and Luna campaigns with an area token limit

Run one fresh campaign each for gpt-5.6-terra and gpt-5.6-luna, with a separate
10000000 reported input-plus-output token allowance for each model. Use the
identical campaign-v025 bedroom state used by Sol, medium effort, subscription
client 0.157.0, fresh decisions, v023 gameplay observations and the same prompt.
The full campaign ends on verified Champion and Hall of Fame completion.

Version red-v0.26 adds an opt-in max_area_tokens limit. Zero disables it for
existing callers. Set it to 1000000 for both trials. At each completed decision
boundary, count all reported input and output tokens since entering the current
game map, including cached input, inspection, invalid and maintenance calls.
A different map ID at the boundary resets the allowance after charging the
exit decision to the previous area. Moving within a map, battles, changing
screens and notes do not reset it. An exit on the threshold decision is allowed.
Save the counter across pause and resume. If the current map reaches the limit,
stop before another model call with reason area_token_budget. Completion and
already-triggered limits keep their original termination reason.

This is a conservative spending guard, not proof that an agent is stuck.
It can stop useful training or exploration in a large map. It does not detect
loops that repeatedly cross map boundaries. The threshold is enforced after
a complete decision and can exceed the allowance by that last call's usage.
No automatic recovery, hints, route choices, state edits or retries are added.
Only the observer sees the monitor metadata. Agent inputs remain unchanged.

Keep Sol's supporting limits: 4000 calls, 60000 raw actions, 4800000 frames,
72000 active wall seconds, 600 frames per requested action phase, 7200 per
dialogue phase, one command per decision and 2048 notebook bytes. Runs are
independent and may execute concurrently. Total allocation is at most 20000000
reported tokens, subject to the existing between-call accounting policy.
Do not substitute models, buy credits, redeem resets or restart failed attempts.

Freeze and hash the runtime before launch. Persist the area counter and map
reset events. Publish separate live pages and final reviews. Reconcile usage,
verify actual text/image message pairs and replay each trace after termination.
Audit the stopping counter against recorded decision boundaries. Preserve
all outcomes, including early stops and infrastructure failures.

Terra and Luna share the same configuration except model identity. Sol's
completed v025 run had no area limit, so its endpoint is a historical reference
with a different stopping policy, not a matched trial. Never overwrite it.
