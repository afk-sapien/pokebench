# Compact journal starter trials, v0.10

All three subscription trials ended without a starter. Each used the same save,
visual policy, low reasoning effort, journal access, and one-million-token budget.
No hints, manual controller actions, restarts, or replacement attempts were used.

| Model | Tokens | Decisions | Actions | Frames | Active wall seconds | Outcome |
|---|---:|---:|---:|---:|---:|---|
| Luna | 995,507 | 184 | 273 | 7,188 | 1,522.89 | Stayed in the house |
| Terra | 996,313 | 142 | 184 | 9,864 | 1,722.05 | Reached Pallet Town |
| Sol | 996,298 | 140 | 208 | 7,738 | 2,010.75 | Reached Pallet Town |

All stopped through token reservation with complete accounting. Total reported
input plus output usage was 2,988,118 tokens. Each ended with an empty party and
no starter completion. None reached the laboratory.

## What happened

Luna first reached the ground floor at decision 14 but never left the house.
It began treating Mom as Professor Oak. From decision 62 onward, its plans
largely tried to advance an imagined starter introduction. It classified 122
decisions as dialogue. The final screen still showed the home conversation.

Terra reached Pallet Town at decision 24. It spent much of its remaining budget
probing the outdoor barrier near the water. Repeated plans sought an opening by
continuing north or south, without reaching the laboratory.

Sol first reached the ground floor at decision 6, then revisited the bedroom.
It reached Pallet Town at decision 77 and later returned home. It repeatedly
described home furniture as the starter setup. By decision 135 it identified
Mom's dialogue. It ended outside again, still without visiting the laboratory.

Locations come from private replay evidence and post-run image inspection. They
were not given to the agents. The viewer's scene descriptions remain the models'
claims, which can be wrong.

## Memory and token findings

None requested a journal write, deletion, or search. Notebook replacements
numbered 113 for Luna, 130 for Terra, and 138 for Sol. These short-task results
do not test whether the new retrieval system helps campaign-length play.

Mean reported tokens per decision were approximately 5,410 for Luna, 7,016 for
Terra, and 7,116 for Sol. Context text averaged 2,052, 2,344, and 2,609 UTF-8 bytes
respectively. Total usage also includes the prompt, images, CLI overhead, and
response. Smaller text does not imply an equal reduction in total tokens.

Compared with the v0.6 million-token pilots, the models received 27, 4, and 2 more
decisions respectively. Completion did not improve. The earlier Sol attempt
reached a visible starter receipt but stopped before final acquisition. This
Sol attempt never reached the laboratory. Multiple policy changes and model
sampling prevent attributing that difference to any single change.

## Verification and provenance

All traces passed deterministic replay. The review validated all 466 recorded
decision images and their source-screen references. Per-decision token sums
matched final usage, numbering was continuous, and no pending calls remained.

The trials used frozen package 0.10.0, benchmark red-v0.10-experimental, and
runtime SHA-256
`523e789b602ea1f2369e4d4286be7314406f08d9fa04ef613a942f1b624ea9b5`.
The starting state and preview are unchanged from starter-repro-v04. Scenario
identity and objective text clarify finishing acquisition and declining a
nickname. The evaluator is unchanged. See the
[predeclared protocol](2026-09-27-starter-v010-protocol.md).

| Model | Verified trace SHA-256 |
|---|---|
| Luna | `294cd1222b2e384251c1115435d4d809b72c4d28f679a1d839bde88f916d4736` |
| Terra | `0974aa10fd2796888107fbdc265e75c363fcdc02bfd33beb0e3c34d393fde8d6` |
| Sol | `07d86ef9d9f81a83209c39af41c23c3427ed5b8c085610df3cc48b17f6d218a5` |

All trials ran uninterrupted. Separate recovery tests exposed a queued-button
release issue after zero-release-frame inputs. Package 0.10.1 restores the
requested release without ticking. That fix did not modify these frozen runs.
The full suite passed 123 tests with private emulator checks enabled. Resumed
and uninterrupted tests produced identical save bytes and verified traces for
both zero and nonzero release durations.

The Luna launcher tool reported exit status 143 after its normal terminal result
was written. Its token-budget checkpoint, usage, and replay agree. Terra and Sol
launcher tools returned zero. There was no extra Luna call or automatic restart.

## Review and interpretation

[Open the local comparison replay](http://127.0.0.1:8942/starter-v010-review.html).
Fixed controls and eight decisions per second give roughly 23 seconds for Luna
and 18 seconds for each other model. Slower playback and highlights are available.

The pipeline supports bounded memory and conservative recovery. These trials
still show perception, navigation, and belief-correction failures. They do not
establish that the interface has no usability problems or that one model is
reliably stronger. A next comparison should isolate presentation changes from
journal instructions before increasing budgets again.
