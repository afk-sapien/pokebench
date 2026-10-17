# Perception isolation protocol

Declared before generation. Diagnostic protocol perception-v012. Production
benchmark v0.11, its starting save, and its scored runs remain unchanged.

## Questions and controlled variables

Use the exact original starting screenshot through the existing subscription
App Server adapter. Test gpt-5.6-luna, gpt-5.6-terra and gpt-5.6-sol at medium
reasoning effort. No API fallback or outside tools. Each perception answer has
its own fresh conversation.

The perception question and output schema are identical across four conditions:

- neutral objective, original 3x presentation
- starter objective, original 3x presentation
- neutral objective, 6x presentation
- starter objective, 6x presentation

The larger image uses the same game pixels, nearest-neighbor enlargement and
same frame header. No labels, highlights or arrows are added. It must downsample
to the original game pixels exactly. The original image must match the recorded
v0.11 model-input hash. Three models and four conditions produce twelve calls.
Counterbalance condition order across models. These single samples cannot
establish a causal effect or reliable model ranking.

Record the complete diagnostic question, final answer, image checksum, model,
effort, runtime source hash, session identity and reported usage locally. Do not
save hidden reasoning. Private scoring notes distinguish visible objects from
invented off-screen objects. They are never included in model requests.

## Action correction

Choose a single shared presentation after inspecting perception results. Prefer
the original size unless the larger size improves factual recognition across the
models without extra confident false claims. Use fresh gameplay sessions with
the original starter objective and unchanged controller semantics. Ask for one
controller action, then show its exact result and request an assessment and a
second controller action. The second response measures correction or accurate
recognition of progress. Execute only valid model-requested actions. If the
remaining allowance covers all three models, request a final observation-only
assessment of the second action. Do not add advice or reference labels.

Private emulator coordinates may check net tile changes offline. No net change
alone does not prove a collision. Inspect the corresponding screenshots before
grading a claim. Preserve malformed actions and rejected requests as failures.

## Spending and starter gate

The shared diagnostic allowance is 100,000 reported input plus output tokens.
Cached input is included in that total and reported separately. Before each
call reserve at least 8,000 tokens, increasing the reservation using the last
context size when available. Stop on missing usage. The subscription client has
no hard per-response ceiling, so record any final-call overrun rather than hide
it. No automatic retries or replacement samples.

Before a starter rerun, the selected presentation must avoid confident bed-as-
stairs errors in both perception conditions for every model. It must also yield
correct or appropriately uncertain action-result assessments for at least two
models. Unsupported claims of entering another room fail the correction check.
Uncertainty about an unseen exit is acceptable. Failure of this gate is a result
and blocks another expensive starter batch. Step five evaluates this gate rather
than automatically launching a batch regardless of the findings.

If the gate passes, predeclare the shared starter configuration and allowance
before launching. Include input, cached input, uncached input, output, gameplay
decisions and summary calls separately. Keep all old results and comparison
groups. Choose the summary threshold and total budget together, with room for
multiple context windows. Do not report these engineering probes as benchmark
achievements or as proof that a model can obtain a starter.
