# Perception isolation results

Diagnostic protocol perception-v012. The production runtime remains frozen.
No starter completion or improved success rate is claimed.

## Status of the five steps

1. Completed neutral perception checks for Luna, Terra and Sol.
2. Completed matched perception checks with the starter objective.
3. Completed both sets at original 3x and lossless 6x enlargement.
4. Partially completed. Luna and Terra each selected and executed one action.
   Sol's first action call failed because the selected model was at capacity.
   The declared missing-usage stop ended generation before correction responses.
5. Evaluated the gate. It is blocked because correction was not measured.
   No new starter batch was launched.

## Findings

All six original-size perception responses avoided confident bed-as-stairs
claims. This is a narrow pass, not proof of accurate scene recognition. Terra
identified the bed confidently with the objective. Other answers included
uncertain furniture interpretations. Sol mentioned a possible open area above
furniture but explicitly left its function uncertain.

The larger image was not consistently better. Luna described the bed as a
visible navigable opening in the neutral 6x condition. Terra gave possible
exit interpretations in both 6x conditions. Sol recognized the bed more clearly
at 6x. Original 3x presentation was therefore retained for every action trial.

The first action response reintroduced a staircase interpretation for both
Luna and Terra. Luna requested left for 16 held and 8 released frames. Terra
requested left for 48 held and 8 released frames. Both moved left within the
same bedroom. Their requested controller actions worked, but their destination
interpretations were unsupported. Neither was subsequently asked to assess
its result because the service failure stopped the batch. These are planning
errors, not evidence that either model failed to correct after feedback.

The objective by itself did not reproduce the shared error in the original-size
perception responses. The action condition changed the prompt, schema, task
and conversation. This suggests a perception-to-action failure worth isolating,
but does not establish which change caused it. Each condition has one sample.
No statistical ranking or causal claim is justified.

## Spending and failure

There were 15 attempted model calls, 14 completed responses and two executed
controller actions. Reported usage is 67,459 tokens: 63,488 input and 3,971
output. Input includes 2,816 cached tokens and 60,672 uncached tokens. No
compaction calls occurred. This is below the 100,000 reported-token allowance,
but actual aggregate usage is unknown because the failed call reported no
usage. Its local event identifies server_overloaded and a model-capacity
message. Missing usage is not treated as zero. No retry, model substitution
or replacement sample was launched.

## Implication

Do not change image size or increase starter budgets based on these results.
The next controlled test should isolate describing the scene before choosing
an action, using the same gameplay prompt and otherwise identical settings.
The model must author its own interpretation and retain uncertainty. No game
labels, map coordinates, correct routes or human corrections should be added.
The unfinished action-result comparison still needs to be completed under a
new declared continuation protocol when service availability permits it.

## Evidence

Exact prompts, images, outputs, sessions, usage, private controller evidence
and diagnostic scripts remain under data/perception-v012. Source hashes and
sanitized counts are in paper/analysis/inputs/perception-v012-audit.json.
Ground-truth grading stayed offline. No production source or game state was
changed. No labels were passed to a model.

[Declared protocol](2026-09-27-perception-protocol.md).
[Local visual comparison](http://127.0.0.1:8942/perception-v012-review.html).
