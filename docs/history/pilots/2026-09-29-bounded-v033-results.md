# Bounded gameplay pipeline validation

Use the [pipeline design](../design/bounded-gameplay-pipeline.md) as the policy
specification. Runtime version is red-v0.33-experimental with package 0.23.0 and
harness codex-app-server-gameplay-v033. Frozen source fingerprint:
`03e81c886b422b77f4f3d04199058ac60a294d51cf5895d8d156b31e37b6cbad`.

## Offline gate

Replay 61 recorded public observations from starter-plan-v028-luna-10m-01 through
the new packet builder with eight-response segments. Reconstructed state matches
the selected public state at every step. Rendered text is byte-identical after
canonical JSON serialization. Total packet text was 157216 bytes versus 894102
bytes for the previous full readable observations, a ratio of 0.176. Median
update text was 2402 bytes. This is a byte-size comparison, not a token-cost or
model-success estimate. No model calls were made for this gate.

The complete test suite passed 237 tests, with two existing tests skipped. New
regressions cover field removals, null and empty values, checkpoint memory,
canonical text, privacy, oversized observations, token admission, segment
boundaries without summary calls and persisted packet state on pause/resume.

## Live gate and complete trial

Run starter-bounded-v033-luna-500k-01 with gpt-5.6-luna at medium effort, from the
same outside-lab v027 fixture. Use a fixed 500000-token ceiling, eight-response
segments and a 12000 observed-context-token threshold. Use the established
controller, observation allowlist and default-name rule. Supply no hint or route.

After eight gameplay decisions and 70767 reported tokens, pause at a committed
boundary. Verify paired actual client text and images, exact packet rendering,
state reconstruction, conversation ordering, token accounting and controller
replay. Resume the same game, notes, plan and remaining budget automatically.
No model turn was repeated, no game state was replaced and no runtime was changed.

The completed run used 481887 reported input plus output tokens across 52 model
calls. All 52 calls executed a gameplay command, verified against the controller
memory log. It used seven conversation segments, zero paid compaction calls,
18 notebook updates and 18 plan updates. Mean tokens per gameplay decision were
9267. Peak input tokens on one call were 17306. The context threshold is checked
between responses and is not a strict backend context cap.

The largest delivered packet was 6082 UTF-8 bytes. Final paired input checks,
state reconstruction, conversation ordering and replay of all 319 raw controller
actions passed. The run ended at the token admission limit without a starter.
Unspent allowance was reserved conservatively for another possible response.

## Interpretation

Earlier retained-history text and JSON pilots averaged about 20620 and 18945
reported tokens per gameplay decision. The new trial had substantially lower
observed token overhead and no paid summarization. The trajectories and token
allowances differ, so this is not a randomized performance or success-rate claim.

Luna continued revisiting lab occupants and making unsupported identity claims.
Its final notes called an observed character or object a sign based on general
text about Professor Oak. That is an agent claim, not a verified environment fact.
Do not add it to the observation layer. The trial did not establish improved
starter-task success. Keep memory correctness, cost efficiency and model gameplay
competence as separate evaluation outcomes.

Private settings, preflight report, gate audit, final audit and exact client
provenance are under data/bounded-v033-luna. The local decision review is
bounded-v033-luna-review.html. ROMs, states, images and raw model histories remain
outside tracked source.
