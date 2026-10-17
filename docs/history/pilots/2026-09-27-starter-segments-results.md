# Starter segments results

Both downstairs and outside checkpoints are now available and reference-verified
locally. The live batch tested outside only. None of Luna, Terra or Sol obtained
a starter from that starting position within the declared allowance.

## Checkpoints

The downstairs snapshot follows action 3 of the existing reference, at frame
338. Its remaining 64 reference actions complete the challenge. The outside
snapshot follows action 7, at frame 888. Its remaining 60 reference actions
complete the challenge. Both snapshots preserve empty parties and unset starter
flags. Their state and screenshot come from the same rendered action boundary.
No setup frames or game-memory changes were added.

The builder verified the original reference, each prefix image and evidence,
and each restored suffix image. Both suffix traces passed the existing success
evaluator and independent deterministic replay. These are reference-controller
checks, not model successes. Raw states and game images remain private.

## Outside model runs

| Model | Decisions | Actions | Reported tokens | Observed progress |
| --- | ---: | ---: | ---: | --- |
| Luna | 22 | 42 | 240,438 | Re-entered home and remained on its ground floor |
| Terra | 20 | 31 | 238,096 | Stayed outdoors, never entered the lab |
| Sol | 17 | 30 | 231,686 | Stayed outdoors, never entered the lab |

All three stopped at token reservation limits with no service failures. No party
member was received in any run. Luna's notes described Oak dialogue and a ball
while the recorded game state and screenshots remained inside the player's
home. Terra and Sol continued trying to navigate outdoor obstacles and reach
buildings. No action reached Oak's laboratory.

Starting outside removed the bedroom traversal requirement, but was insufficient
for success in these single attempts. The result does not prove that any model
cannot complete the segment with a different budget or interface. It does show
that these failures are not confined to leaving the initial bedroom. The
starting-state change and removal of the now-inaccurate start-at-home phrase
are explicit scenario differences, not a claimed causal framework improvement.

## Accounting and validation

Total reported usage was 710,220 tokens across 59 calls and 103 controller
actions, below the combined 750,000 allowance. Input tokens were 696,843 and
output tokens were 13,377. Input includes 558,592 cached tokens and 138,251
uncached tokens. Each model stayed below 250,000 tokens. No context summary
occurred. Accounting is complete for this batch.

Model settings, limits, core and frozen production source matched the prior
baseline. The starting state and objective description were the declared
scenario changes. Every recorded controller action passed replay, and the
review export verified model-input image hashes against recorded game pixels.
No object labels, route hints or reference actions were provided to a model.

The downstairs checkpoint has not received a live model batch. Its readiness
means fixture validation, not measured model performance. Starting outside is
a separate benchmark condition and grants no credit for the original task.

[Protocol](2026-09-27-starter-segments-protocol.md).
[Outside-start review](http://127.0.0.1:8942/starter-outside-v014-review.html).
[Checkpoint workflow](../challenges.md#verified-starter-segments).
