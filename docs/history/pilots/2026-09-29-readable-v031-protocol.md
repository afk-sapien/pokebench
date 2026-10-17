# Readable observation presentation

Version red-v0.31-experimental, package 0.22.0, adds an opt-in deterministic
text renderer for the assisted gameplay track. Select it with
`--observation-format text`. JSON remains the default and the already-running
v030 conversation comparison uses its frozen original runtime. Do not change
that comparison's observation format or use its results as a test of this change.

The formatter receives only the payload produced by the existing public
observation boundary. It does not read the emulator, evaluator or run directory.
It has no model calls and adds no hints, inferred object identities or routes.
The screenshot and response schema stay unchanged. The input format is tracked
in the provider configuration and preserved on resume. Observation policy remains
player-information-v028. The text presentation protocol is observed-gameplay-text-v1.

Separate current game state, the latest command result, agent-authored plans and
notes, action history, exact dialogue and other memory. Format each recent action
as a line containing requested action and count, observed starting and ending
coordinates, facing, actual outcome and matching-result count. Attach the exact
retained dialogue when an encounter reference resolves. Report unavailable
references and transcript truncation explicitly. Preserve the 50-decision limit,
chronology, other public fields, map rows, budget, party, bag and inspection data.

Keep the canonical structured model_context and record the exact model_input_text
sent to the model. Use the same text rendering for compaction requests so a summary
turn does not silently switch input styles. Auditors of text trials must match
model_input_text verbatim in the actual client message, with the associated image.
Existing JSON-only audit scripts are insufficient for text trials.

This is a formatting implementation, not a semantic summary. Retain old redundant
memory fields in this version to avoid combining information removal with a
presentation change. It may improve readability, but token savings and successful
play are not established. Test on the same model, scenario, context policy and
budget after the context comparison. Do not present the formatting test suite as
evidence of improved model performance.

## Authorized paired pilot

Run one new text trial and one new JSON control on the same frozen v031 runtime.
Use gpt-5.6-luna, medium effort, retained conversation and 32000-token periodic
compaction in both conditions. Start each from the untouched outside-lab v027
fixture with empty agent notes and history. The objective is obtaining a starter
with its default name. Each condition gets 250000 reported input plus output
tokens, including cached input and summaries, for 500000 aggregate tokens.
Use the same supporting limits as the v030 pilot. Run text first, then JSON,
without intervention, restarts or budget extensions based on results.

Verify text rendering against the canonical public payload, then match its exact
bytes and associated screenshot in the same actual client message. Match JSON
payloads and images similarly. Verify shared conversation history and summary
handoffs. Reconcile token totals and replay both controller traces. Export a
combined local review using a temporary generated file to avoid overwriting the
single-run review through the exporter's output-exists guard.

Report both outcomes regardless of direction. One trial per condition is an
engineering pilot, not a statistical performance claim. These equal token caps
may yield different action counts. Keep the earlier v030 trials separate.

## Pilot outcome

Both trials finished at their token allowance without acquiring a starter.
Text used 247438 tokens for 13 calls, including one summary and 12 gameplay
decisions. JSON used 246290 tokens for 14 calls, including one summary and
13 gameplay decisions. Total reported usage was 493728 tokens.

Both had two retained conversations. Actual client messages verified the recorded
input and screenshot pairs, sequential conversation history and summary handoff.
Both controller traces replayed successfully. Cross-checks found identical
runtime, checkpoint, limits, model, effort and prompt. The only agent-configuration
differences were observation_format and text_presentation.

Text auditing initially stopped because the canonical JSON log sorted field keys
and the v031 renderer used insertion order. The preserved text matched actual
client messages exactly. Regeneration reproduced every line and its multiplicity
but not dictionary field order. Record this audit limitation, preserve the failure
and repair artifacts, and continue only the unstarted JSON trial. No model call
was repeated. The v032 order repair is separate from these frozen v031 results.

No starter-success improvement was demonstrated in this small pilot. Retained
context consumed the budget in only 12 or 13 gameplay decisions. This limits
conclusions about eventual task completion. Do not claim that text is always
better or worse, or that a formatting check proves improved planning.
