# Luna starter trial with one million tokens

The owner requested a 1000000-token trial after the completed 500000-token pilot.
Run starter-bounded-v033-luna-1m-01 as a new attempt from the same outside-lab v027
fixture. The earlier trial ended at its token limit and is preserved unchanged.
This new attempt does not continue its saved game, notes or model conversation.

Retain the exact v033 frozen runtime, gpt-5.6-luna, medium effort, eight-response
segments, 12000 observed-context-token threshold, deterministic checkpoints and
zero paid summaries. Retain all supporting limits and the same eight-call audit
gate. Only the total reported input-plus-output token allowance increases from
500000 to 1000000. Cached input counts toward this allowance. Reserve usage before
requests as in the existing pipeline. No hints, interventions, retries or budget
extensions based on the outcome.

Stop on verified starter acquisition or an existing limit. Verify exact client
input and screenshot pairs, state reconstruction, conversation ordering, usage
and controller replay. Publish a local live page and completed decision replay.
Report the result as one higher-budget trial, not a success-rate estimate.

## Measured outcome

The run ended at the token budget without obtaining a starter. It used 980408
reported tokens across 105 gameplay decisions, with 961958 input tokens and
18450 output tokens. The remaining allowance was insufficient for another
request under the conservative budget preflight. There were 15 conversation
segments and no paid summaries.

Exact paired input delivery, state reconstruction, conversation order and
controller replay all passed. Replay covered 604 controller actions and
18366 frames. The largest text packet was 6928 UTF-8 bytes.

The local review is available at
http://127.0.0.1:8942/bounded-v033-luna-1m-review.html. This single attempt
does not establish a success rate or isolate the cause of failure.
