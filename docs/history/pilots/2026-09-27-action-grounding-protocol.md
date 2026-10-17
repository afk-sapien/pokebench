# Action grounding diagnostic protocol

Declared before new generation. Protocol action-grounding-v013. Production
v0.11 remains frozen. This is a continuation and controlled diagnostic, not a
replacement for the preserved perception-v012 trials.

## Continuation

Resume the completed Luna and Terra action conversations at their recorded
turns. Restore their cumulative usage before requesting another turn. Replay
only their recorded controller action from the original save and verify the
resulting screenshot hash. Request assessment and a second action, then a final
observation-only assessment. Sol receives one explicitly recorded technical
replacement for its capacity-failed initial call, followed by the same checks.
The prior failed call and its unknown usage remain in the old ledger.
Continuation has a separate 50,000 reported-token scheduling allowance.

## Controlled comparison

For each of Luna, Terra and Sol, start fresh baseline and observation-first
conversations from the same starter save. Medium effort, original 3x current
image, controller timing, objective, nickname rule, response schema and action
limits are identical. The baseline is the v012 action diagnostic prompt, not
an exact reproduction of the production simple response contract.

The treatment adds only this instruction:

> Before choosing each controller action, use previous_result to briefly
> describe what is visible in CURRENT, distinguish uncertain interpretations,
> and assess the preceding action when there is one. Base the action on that
> observation.

Both arms return the same fields with the same length limits. Description and
action are generated in the same response. This tests an instruction to ground
actions, not a separate perception model or a two-call architecture.

Each arm requests four individual actions and a final observation-only
assessment. The budget is 40,000 reported tokens per arm, with 240,000 across
six arms. Baseline precedes treatment for Luna and Sol. Treatment precedes
baseline for Terra. Calls are interleaved by decision number. Sessions preserve
history. No compaction is expected in these short trials. Keep every attempt,
including malformed responses, service failures and reservation stops.

## Accounting and failure handling

Reserve at least 8,000 tokens per call, or the preceding context size plus
4,096 if larger. Count cached input in reported totals and also disclose it
separately. A failed call without usage consumes its full reservation for
scheduling purposes, but its actual usage remains unknown. The client does not
provide a hard output ceiling. Disclose any final-call overrun.

A capacity failure disables further calls for that model in this invocation.
Continue unaffected models so a service failure does not discard useful work.
Do not substitute a model or retry automatically. Other failures stop generation
for inspection. Missing model comparisons block the starter gate.

## Offline measures and gate

Never feed ground truth back to the model. Use saved frames and private emulator
state only for offline evaluation. Record unsupported exits or room changes,
correction after feedback, repeated ineffective inputs, tokens, and unique
visited map/x/y locations. No net tile change alone proves a collision. Inspect
screenshots before judging an ineffective input or a visual claim.

A starter batch requires all six arms to complete. The treatment must improve
unique-location coverage for at least two models without reducing it for the
third. Each treatment must correctly or cautiously assess at least three of
its four action results, with no unsupported claim of a room transition and no
repeated commitment to a disproved exit. These are engineering gates, not
statistical significance or proof of broad gameplay ability. Single samples
cannot establish a model ranking.

If the gate passes, freeze a separately versioned common starter configuration
and declare its budget before running all three models. If it does not pass,
report the failed or inconclusive comparison without another starter batch.
