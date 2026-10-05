# Bounded gameplay pipeline

## Diagnosis and decision

Previous experiments combined incompatible memory policies. Fresh-turn runs
needed repeated history. Retained conversations then received that same history
again on every turn. A separate compaction request reread the accumulated input,
added another current observation and screenshot, and produced a short summary.
The 250000-token pilots consequently permitted only 12 or 13 gameplay decisions.
Changing JSON to prose did not address this architecture.

Use short retained conversation segments with deterministic checkpoints and state
updates. Do not use paid summarization in this policy. Keep the old providers for
reproducibility. Do not silently resume old runs with the new policy.

## Information ownership

The controller remains responsible for actual emulator actions and observed
results. The evaluator remains private and decides completion. Neither chooses
routes, changes goals, supplies quest prerequisites or diagnoses model mistakes.
The existing observation allowlist remains the only information source.

The observation archive keeps the existing 50-decision history, encountered
dialogue and explored terrain outside model context. The model owns a bounded
notebook and current goal with evidence and a completion condition. These remain
fallible claims. The model updates them during ordinary gameplay responses.
No separate model call is required to maintain or summarize them.

## Conversation segments

Retain up to eight model responses or 12000 observed context tokens, whichever
comes first. Check boundaries before the next request. The threshold can be
exceeded by the last response in a segment. It is not a backend context hard cap.
At a boundary, close the conversation and start a new one with a deterministic
snapshot. This advances no game frames and consumes no separate model turn.

The snapshot contains the current public state, the agent notebook and plan,
known local explored map, up to eight recent observed decisions under 3072 bytes,
and recent exact dialogue under 2048 bytes. Explicit omission counts distinguish
missing recall from absence of events. The complete allowed recall remains
available through inspect memory. No guessed summary replaces original dialogue.

Within the segment, send current location and the latest controller result once,
plus replacements for changed screen, map, party, bag, money, badges and battle
fields. Unchanged fields remain in the retained conversation. Include explicit
removed-field names so disappearing values cannot remain falsely current.
An empty list, null and an absent field have distinct meanings. Carry sequence
numbers and a base-sequence reference. A new segment always starts with a complete
state snapshot, never a delta against a discarded conversation.

Send notes and the active plan only on changes, or in every new snapshot. Keep
current token allowance visible. Attach the current screenshot, plus a previous
one only on explicit look-back. Old images disappear with the discarded segment.
Raw animation feedback and legacy duplicate history are excluded. Controller
validation errors remain visible so the model can correct invalid actions.

## Bounds and accounting

Limit ordinary packet text to 32000 UTF-8 bytes. Explicit inspect responses may
use up to 64000 bytes and are still metered. An oversized packet stops before a
model call with an observation-budget reason, rather than silently deleting
current game facts. This is an explicit limitation for unusually large storage
inspections until a paged inspection interface is introduced.

Perform budget admission after constructing the actual next packet and deciding
whether a new segment is needed. Use a conservative byte-based text reservation,
image allowance and output reserve. Preserve reported input, cached input and
output separately. Total benchmark tokens still include cached input. This is
reported-between-calls enforcement, not a guaranteed backend generation cap.

Every model request must produce an ordinary action or an explicit look-back.
There are zero paid compaction calls. Log segment boundaries, exact sent text,
canonical packets, full public audit observations, usage and controller outcomes.
Persist the current baseline, packet sequence and segment count with the model
session checkpoint so resume cannot apply updates to the wrong state.

## Validation before model spending

Test delta reconstruction including removals and empty values, deterministic
text after log serialization, reset and resume boundaries, error feedback,
notebook preservation, public-only fields, packet bounds and no summary requests.
Replay recorded observations offline to measure packet size and repeated-input
reduction. Report bytes as bytes, not as tokenizer-exact estimates.

After those checks, freeze the runtime and run one Luna starter trial capped at
500000 total tokens. Pause after eight calls for a wiring check, then resume the
same trial and budget only if packets, session continuity and accounting pass.
Do not restart the game, add hints, increase the budget or change code mid-trial.
Audit exact client input, controller replay and total usage at completion.

Judge two separate outcomes: token efficiency and actual game progress. A cheaper
pipeline is an engineering improvement. It is not proof that the model plans
correctly. A single trial is not a model ranking or a success-rate estimate.
