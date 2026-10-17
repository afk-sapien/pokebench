# Starter baseline repeat protocol

The user requested another benchmark run after the action-grounding comparison.
This batch repeats the existing v0.11 starter baseline. It is not promotion of
the failed observation-first treatment and does not claim a framework fix.
Keep the original attempts and the new attempts in the same settings group,
with distinct run identifiers ending in 02.

Run gpt-5.6-luna, gpt-5.6-terra and gpt-5.6-sol with medium effort. Use the same
starter-v010 save, visual track, original 3x current screenshot, continuous
conversation, simple response contract, no hints, and no nicknames. Retain the
24,000-token metered summary threshold and all original limits. Each run has
250,000 reported input plus output tokens with reservation before new calls,
100 model calls, 300 actions, two actions per decision, 600 frames per action,
120,000 total frames and 1,800 seconds. The combined reported allowance is
750,000 tokens. The client cannot guarantee a hard final-response ceiling.

Use the original frozen production source hash. Confirm manifest parity for
prompt, scenario, core, model effort, provider policy and limits. Exact settings
do not imply deterministic model sampling or an unchanged backend deployment.

No automatic retry, model substitution or budget increase is authorized by
this protocol. A failed model call stops its run. Preserve unknown usage as
unknown. Other models may finish their independently capped runs. Stop on
objective completion. Report success, stop reason, decisions, actions, input,
output, cached input, context maintenance and observed progress. Verify replay
and export a review for every run with usable recorded decisions.

These short-budget repeats measure variation under the prior allowance. They
are not long-horizon or compaction tests. Previous runs used their allowance
before reaching the context threshold, and that limitation remains explicit.
