# Terra and Sol starter comparison

Run one fresh trial each for gpt-5.6-terra and gpt-5.6-sol using the exact
frozen runtime, outside-lab save, prompt, medium reasoning effort, observation
policy, context settings and supporting limits of starter-bounded-v033-luna-1m-01.
Each model receives a 1000000-token ceiling including cached input. Only the
model and output identifiers change. No paid summaries or injected quest hints.

Pause each trial after eight calls to verify delivered text and images, state
reconstruction, conversation ordering, usage and controller replay. Resume the
same trial and remaining budget automatically when the gate passes. Stop on
verified starter acquisition or an existing limit, then audit the final result.
One attempt per model does not establish a success rate.

## Measured results

| Model | Starter acquired | Tokens | Decisions | Segments |
| --- | --- | ---: | ---: | ---: |
| Luna | No | 980,408 | 105 | 15 |
| Terra | Yes | 298,088 | 32 | 5 |
| Sol | Yes | 144,746 | 16 | 3 |

Terra and Sol both acquired Charmander and declined the nickname prompt.
Both completed before their token limits. Sol took about 73 seconds and Terra
about 139 seconds of recorded run wall time. Luna previously stopped at the
budget limit without a starter. All three used zero paid summaries and passed
exact input delivery, state reconstruction, conversation order and controller
replay checks.

Sol recognized the missing Oak prerequisite, left the lab, triggered the north
exit event and returned for starter selection. Terra also completed this
sequence after more lab exploration. This demonstrates that the current
interface supports completion by both models on this checkpoint. One attempt
per model does not establish success rates or isolate the cause of Luna's failure.

The combined local decision review is available at
http://127.0.0.1:8942/bounded-v033-model-comparison-review.html.
