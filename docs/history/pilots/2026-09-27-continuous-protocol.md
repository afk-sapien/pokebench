# Continuous harness development protocol

Declared before model generation. Benchmark red-v0.11-experimental.
This is development, not a statistically powered model ranking.

## Budget and sequence

Total planned allowance is 1,200,000 reported input plus output tokens across
all stages, including compaction. Cached input remains included. Subscription
limits do not expose a strict per-response output cap here. Reservations stop
new calls near the allowance, but a final response can exceed an estimate.
Record any overrun. Stop the experiment if usage becomes unavailable.

- Engineering smoke and compaction validation: at most 30,000 tokens total.
- Continuity diagnostic: Luna, Terra and Sol, fresh versus continuous, 35,000
  tokens each. Six trials, 210,000 tokens maximum planned allocation.
- Sol development ablations: simple strip, simple current, simple current at
  medium effort. 35,000 tokens each, 105,000 total. The continuous assessment
  strip from the preceding stage is the reference.
- Starter task: all three models using the same frozen selected configuration,
  250,000 tokens each, 750,000 total. Exact original starter save, unchanged goal.
- The remaining 105,000 tokens are an overrun reserve, not permission to run
  additional replacement trials. Failed attempts are retained.

Exact models: gpt-5.6-luna, gpt-5.6-terra, gpt-5.6-sol. Subscription authentication
only. No API fallback, hints, human control, object labels or hidden-state inputs.

The diagnostic checkpoint is derived from the existing Terra v0.10 trace after
decision 25, outdoors. Reproduce its actions and screenshot hashes before saving.
All diagnostic arms receive the same bytes and objective. This checkpoint is
for development only and does not count as starting from home.

Continuity arms use the same assessment schema, 2x strip, low effort and explicit
hold/release controller. Prompt differences state whether history persists.
Simple-schema and current-frame arms use the same controller advice. Medium
changes effort only. Selection considers valid accounting first, then observed
progress and error recovery per reported token. With one trial per arm, effects
are descriptive and uncertain. Sol-guided selection is disclosed.

## New contract

The current image is a fixed 3x enlargement with a frame header. Up to eight
recent decision images may be recalled by an explicit look_back request.
This does not label game objects or advance emulation. The model returns actions,
nullable short notes, and nullable look_back. No object inventory is required.

Hold/release/wait semantics are unchanged. Suggested timings are walking 16/8,
clear walking 48/8, A or B tap 8/24, and neutral wait 60/0. These are suggestions,
not automatic input substitutions. Every executed frame is counted.

Each persistent App Server conversation uses the exact requested model and
explicit effort. Outside integrations and tools are disabled. The installed
client still reports the global writing preference file as an instruction
source. Only its audited SHA-256 is accepted:
70a4ca34d487912d4cf511d1033abbce1bce95ab94c305a28912e406c6e4aae3.
It contains punctuation preferences and no gameplay information. Other outside
instruction sources invalidate the run. User configuration is not edited.

Compaction is requested at a recorded context threshold, initially 24,000 tokens.
It is a separate maintenance decision with zero controller actions. Usage must
increase monotonically and be reported. Missing compaction accounting stops the
run. The provider records cumulative usage deltas rather than recounting totals.
Session IDs, latest turn IDs, notes, recall buffers and usage survive checkpointing.
Resume verifies the latest completed model turn matches the emulator checkpoint.
No automatic retries or silent fresh conversations are allowed on recovery.

## Validation and reporting

Run unit tests, real-emulator recovery checks, and offline timing diagnostics.
Validate a real subscription turn, explicit compaction accounting and continuation
before spending on the model comparisons. Freeze runtime source before each
stage. Do not edit a running trial's configuration or source.

Report every attempt, tokens, calls, maintenance calls, controller actions,
game frames, wall time, completion and accounting status. Replay and validate
all completed gameplay traces. Export a fast decision review. Preserve v0.10
results and separate comparison groups by source and provider configuration.

## Engineering amendment before development trials

The first live smoke test used 5,132 reported tokens for its controller decision.
Native compaction then returned unchanged cumulative usage and zero input and
output increments. The guard stopped the trial with accounting_complete=false.
The saved rollout confirmed the same missing accounting. That attempt remains
an engineering failure with an unknown compaction cost. No diagnostic or starter
trials ran under that implementation.

Use metered agent-summary compaction instead. A normal generation turn writes a
bounded, agent-authored handoff. Its usage is recorded. The provider explicitly
rotates the conversation and supplies that summary with the next game observation.
No game frames advance. Native opaque compaction is disabled. The model keeps a
continuous history between these declared rotations. This does not claim to
preserve opaque reasoning across rotation. The engineering failure remains
excluded from fully accounted benchmark comparisons and is never reported as
zero-cost compaction. The experiment allocation remains unchanged, with the
unknown engineering compaction cost explicitly disclosed.
