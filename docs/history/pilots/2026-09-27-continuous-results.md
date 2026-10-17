# Continuous visual starter trials, v0.11

All three trials stopped through token reservation without obtaining a starter.
The runtime was frozen, and all trials used medium effort, a continuous session,
a simple response contract, current-frame images and a 250,000-token allowance.
No hints, human inputs, retries or changes were supplied during gameplay.

| Model | Reported tokens | Calls | Actions | Outcome |
|---|---:|---:|---:|---|
| Luna | 234,730 | 19 | 38 | Stayed in the bedroom |
| Sol | 237,188 | 20 | 26 | Reached Pallet Town |
| Terra | 229,694 | 19 | 27 | Reached the ground floor |

All starter traces passed deterministic replay. Recorded image inputs and source
screens passed review validation. Token sums match final usage, with complete
accounting for all development and starter trials.

## Interpretation

The nine short development comparisons did not establish a clear winning setup.
Luna retained a false laboratory interpretation with both fresh and continuous
assessment contexts. None of the diagnostic arms reached the lab. The final
candidate tests the recommended design and is not an empirically selected winner.

The starter results do not demonstrate improved completion. Sol reached outdoors
within this smaller allowance, but effort, presentation, schema, context and
budget differ from earlier protocols. A causal improvement or model ranking
cannot be inferred from these single trials.

Continuous history raised reported tokens per decision. The starter trials never
reached the 24,000-token context threshold, so none exercised compaction. Thus
context rotation works in engineering checks but its gameplay benefit remains
unmeasured. A lower threshold is a future controlled experiment, not a change
applied to these runs. The total budget and context threshold must be tuned
separately. Larger history is not inherently more token-efficient.

## Engineering and spending

The first native compaction returned unchanged cumulative usage. Its guard
stopped the engineering attempt. The local rollout confirmed missing accounting.
Metered agent-authored summaries replace native compaction in scored trials.
A live pause/resume check completed a charged summary and resumed gameplay
after session rotation. An intermediate smoke trial stopped early because
its token reservation could not fit another call. All attempts are preserved.

Total reported usage across engineering, development and starter trials was 985,710 tokens.
An additional native-compaction cost is unknown, so this is not a fully accounted
experiment-wide total. All later development and starter trial usage is complete.
No further replacement trials were launched.

Validation: 136 tests passed with private emulator recovery enabled, plus Ruff
and 15 offline controller timing probes. The probes do not prove an input always
has the same gameplay effect across animations or dialogue states.

[Starter review](http://127.0.0.1:8942/starter-v011-review.html) and
[development review](http://127.0.0.1:8942/continuous-development-v011.html).
[Protocol](2026-09-27-continuous-protocol.md) and
[implementation guide](../continuous-play.md) describe budgets and recovery.
