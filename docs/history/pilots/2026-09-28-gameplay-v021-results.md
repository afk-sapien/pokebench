# Retained conversation gameplay results v021

All four models formally earned Brock's badge. None obtained a starter within
the unchanged 250,000-token cap. The eight attempts used 1,442,857
reported tokens out of the 2,000,000 allocation. No retry, reset credit or longer
campaign run was used. Subscription usage was recorded without an API dollar
price estimate.

| Model | Task | Reported tokens | Controller decisions | Compactions | Result |
| --- | --- | ---: | ---: | ---: | --- |
| Luna | Brock | 141,435 | 8 | 0 | Badge confirmed |
| Luna | Starter | 225,863 | 16 | 0 | Bedroom, no starter |
| Terra | Brock | 206,685 | 13 | 1 | Badge confirmed |
| Terra | Starter | 237,281 | 17 | 0 | Ground floor, no starter |
| Sol | Brock | 121,534 | 9 | 0 | Badge confirmed |
| Sol | Starter | 245,885 | 18 | 0 | Pallet Town, no starter |
| Astra | Brock | 37,047 | 4 | 0 | Badge confirmed |
| Astra | Starter | 227,127 | 17 | 0 | Oak's lab, no starter |

## What changed and what was verified

The v020 interface batches continue-only dialogue and corrects menu labels.
These v021 trials additionally retained conversation history, with the existing
metered summary threshold of 24,000 context tokens. Both tasks kept the original
save states, medium effort, model identities, 2,048-byte notebook, and v019 run
caps. The new dialogue phase had a 7,200-frame ceiling inside remaining run
budgets. All attempt settings matched within each task.

Every recorded text payload and current image was verified in actual client
history. Normal decisions reused the same session. Terra's Brock attempt invoked
one charged compaction, then received the exact handoff in a new session. The
other attempts did not reach the compaction threshold before completing or
stopping. All eight controller traces replayed with matching screenshots,
evaluator evidence and final scores. Usage sums were complete and every attempt
remained under its cap.

## Comparison with v019

Formal Brock completion increased from one of four attempts to four of four.
The Brock attempts used 506,701 tokens, compared with 957,992 previously,
a 47.1% reduction. Astra completed in four
controller decisions and 37,047 reported tokens. The new pipeline successfully
removes the repeated model calls formerly needed for reward text.

Starter completion remained zero of four. Luna stayed in the bedroom. Terra
reached the ground floor. Sol reached Pallet Town. Astra followed Oak into the
lab but stopped before acquiring a Pokemon. All four final parties were empty.
These attempts made only 16 to 18 controller decisions, compared with 40 to 56
previously. Retained conversations made each call larger under a budget that
counts cached input tokens as well as new input and output. No claim is made
that this reported token total equals subscription cost or money billed.

Dialogue, menu handling and context retention changed together. This batch shows
a better system outcome for Brock, but cannot isolate the effect of each change.
It does not establish a stable model ranking or a general improvement in
navigation. Earlier false location assumptions can persist in retained history.
The trials do not show that memory retention alone is sufficient to solve them.

The next diagnostic should compare fresh and retained contexts with the same
v020 interface and fixture, then examine navigation-specific failures. Keep
budgets fixed and do not provide a route or correct destination to the agent.
Do not launch a full campaign based on the battle result alone.

[Open the review](http://127.0.0.1:8942/gameplay-v021-review.html).
The protocol is `2026-09-28-gameplay-v021-protocol.md`. Sanitized evidence is
`paper/analysis/inputs/gameplay-v021-audit.json`. Raw controller logs, images,
client histories and save states remain private under the ignored run directories.

Validation: all 103 actual model messages contained their exact recorded text
and current image together. The repository test suite passed 176 tests, with
two optional emulator checks skipped. Lint passed. The manuscript keeps its
original baseline snapshot and incorporates this batch through its separate
audited input.

The rebuilt manuscript has 4,964 main-text words. Its reported Flesch-Kincaid
grade is 10.9 and reading ease is 38. The scaffold verification gate passed,
including formatting, provenance, declarations and PDF/Word freshness.
