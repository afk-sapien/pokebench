# Retained conversation comparison

Version red-v0.30-experimental uses package 0.21.0 and gameplay harness
codex-app-server-gameplay-v030. Retained conversation was already supported.
Previous trial launchers explicitly enabled fresh decisions to reduce input
usage. New gameplay launches use retained conversations unless fresh decisions
is explicitly requested for a comparison. Increase the default gameplay
compaction threshold from 12000 to 32000 context tokens. Explicit old settings
remain available and frozen past runs are unchanged.

Keep complete model conversations between decisions. On reaching the context
threshold, request an agent-authored summary in the same conversation, charge
its input and output tokens, and execute no controller action. Start a fresh
conversation with that summary and the current observation on the next turn.
The separate notebook, active plan and observed 50-decision history survive.
Summary statements remain fallible agent claims. Old screenshots leave the new
conversation. The eight-image look-back buffer remains available. Do not prune
arbitrary messages or summarize every action.

The threshold is checked between calls, not a strict context cap. The summary
request itself includes current observations and can exceed the threshold.
The model receives no walkthrough, prerequisite or reviewer feedback. Existing
observation and summary prompts remain unchanged apart from the already-tested
v029 plan clarification. Observation policy stays player-information-v028.

## Paired pilot

Run gpt-5.6-luna with medium effort on the identical outside-lab v027 fixture.
One trial retains conversations and one explicitly starts fresh each decision.
Use 32000 for the configured threshold in both trials, ignored in fresh mode.
Each gets 250000 total reported input plus output tokens, including cached input
and summary calls. The aggregate allowance is 500000. Reserve estimated usage
before each request, with the existing reported-between-decisions limitation.
Keep all other limits, scenario, objective, observations and controller policy
identical. Do not reuse previous plans or failed-run memories. The only prompt
difference states whether the conversation persists. Freeze the common runtime.
Run sequentially, retained first. No retries or extensions based on results.

Verify actual text and screenshots in the same client message. Verify retained
sessions contain successive user observations and assistant responses. Verify
summaries are delivered to the first subsequent new session. Verify fresh mode
uses distinct sessions and no summaries. Reconcile all token usage and replay
both controller traces. Record any invalid response or infrastructure failure.
Export a combined review and private audit. Keep ROMs, saves and raw client
histories private.

This is a small engineering pilot with one trial per condition, not a statistical
success-rate claim. Equal total token budgets permit fewer decisions with retained
history. Report calls, gameplay decisions, compactions, milestones and usage
separately. Failure to acquire a starter within this budget does not show that
continuity has no effect. Presence of summaries does not establish better play.

## Pilot outcome

Both trials stopped at their token allowance without obtaining a starter.
Retained mode used 247552 tokens for 14 model calls, including one summary,
across two conversations. Fresh mode used 238921 tokens for 34 calls across
34 conversations. Total reported usage was 486473 tokens.

Actual paired text and image delivery verified for both runs. Successive user
observations and assistant responses occurred in the same retained conversation.
The summary reached the next conversation, and the summary turn advanced no
game frames. Both controller traces replayed successfully. This demonstrates
that continuity and metered compaction work, not that they solve the task.
The small equal-token allowance also permits fewer actions in retained mode.

The supervisor encountered an output-exists guard when replacing its initial
single-run review with the combined review. Both trials and their individual
audits had already completed. Export the combined review to a new filename,
preserve the exception and repair record, and update the live link. No trial
was restarted and no game log was modified.
