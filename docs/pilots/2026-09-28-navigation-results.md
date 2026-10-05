# Navigation repair results

The final v023 batch acquired a starter with Sol and Astra. Luna and Terra did
not finish. The preceding v021 batch had no starter completions. These are one
attempt per model per version, not reliable success-rate estimates. Both repair
batches together used 1,708,364 reported tokens within the declared 2,000,000
cycle allocation. No extra retries, reset credits or campaign run were used.

| Batch | Model | Reported tokens | Controller decisions | Compactions | Result |
| --- | --- | ---: | ---: | ---: | --- |
| navigation-v022 | Luna | 235,834 | 21 | 3 | Bedroom, no starter |
| navigation-v022 | Terra | 244,526 | 19 | 4 | Lab, no starter |
| navigation-v022 | Sol | 208,768 | 17 | 3 | Starter confirmed |
| navigation-v022 | Astra | 247,686 | 20 | 4 | Pallet Town, no starter |
| navigation-v023 | Luna | 244,529 | 50 | 0 | Lab, no starter |
| navigation-v023 | Terra | 241,639 | 37 | 0 | Pallet Town, no starter |
| navigation-v023 | Sol | 110,146 | 18 | 0 | Starter confirmed |
| navigation-v023 | Astra | 175,236 | 26 | 0 | Starter confirmed |

## Confirmed framework defects and corrections

A partially successful movement could report no movement after hitting an
obstruction. The new result reports actual same-map displacement and positions,
including progress in the input that reaches a global stop. Map transitions and
scripted input locks previously returned control before the game was ready.
The collector now passively settles them within recorded run limits.

The starter Pokedex preview was classified as overworld control. Its description
and dismissal required extra model calls, while movement appeared available.
The corrected interface captures that visible card, advances its confirmed
continue-only wait, and stops before YES/NO. Unknown modal screens suppress the
map and movement. No emulator hooks or memory patches are used.

Models now receive a bounded grid of previously observed terrain and the last
eight movement outcomes. Unseen cells stay unknown. Straight-line movement can
request up to eight tiles, with the same obstruction and transition stops.
The prompt is shorter and the model still chooses every direction, destination,
interaction and menu response. The original visual track remains unchanged.

## What the model traces show

In v022, Sol finished. Terra reached starter confirmation but used its remaining
budget on preview-screen handling and a context handoff. Astra visited the lab
before triggering Oak, then ran out while exploring town. Luna stayed in the
bedroom, repeatedly acting on an incorrect guess about the stairs.

The v023 batch additionally fixes the modal screen and uses fresh decisions with
bounded notes and observed-state memory. It makes no paid summary calls. Sol and
Astra both completed acquisition, declined the nickname, and reached the formal
completion condition. Luna left the house and reached the lab, but repeatedly
examined a ball before completing Oak's introduction. The visible dialogue kept
saying that the balls contain Pokemon. Terra explored the lab, mistook aides for
Oak, corrected that belief, and ran out of budget while navigating town.

More decisions helped expose these failures but did not guarantee completion.
The final Luna and Terra traces still show ineffective exploration and repeated
assumptions despite usable controls and contrary observed text. These runs do
not prove that every remaining failure belongs to the model or that the framework
is complete. They do show that these concrete controller defects were removable,
and that Sol and Astra can finish the unchanged task within this cap.

Context policy and modal handling changed together between the two repair
batches. Do not attribute the completion difference to either alone. Sol also
completed the earlier repaired batch. Further model comparisons need repetitions
on a frozen policy, rather than more changes combined with a larger budget.
Fresh decisions are explicit in the v023 run configuration and recommended
example. Retained context remains available for separate memory experiments.

## Validation and artifacts

All eight raw controller traces passed deterministic replay, including screenshots
and evaluator evidence. Every recorded text payload and current image appeared
together in the actual client message. Token totals reconcile with all calls,
including summaries. Every attempt stayed below 250,000 reported tokens.
Subscription usage is reported without an invented API dollar cost.

Separate offline controller checks completed the unchanged starter fixture and
replayed the previous successful Brock command sequence. Both passed replay.
These deterministic checks used explicit reference controls and no model calls.
They are not counted as model successes or supplied as model hints.

The repository suite passed 185 tests with two optional emulator checks skipped.
Lint passed. A transient GitHub dependency timeout was bypassed with the already
installed pinned environment. No dependency version or benchmark state changed.

[Final v023 review](http://127.0.0.1:8942/navigation-v023-review.html).
[Preserved v022 review](http://127.0.0.1:8942/navigation-v022-review.html).
The declared protocols are `2026-09-28-navigation-v022-protocol.md` and
`2026-09-28-navigation-v023-protocol.md`. Sanitized results live in separate
`paper/analysis/inputs/navigation-v022-audit.json` and
`paper/analysis/inputs/navigation-v023-audit.json` files. The original manuscript
baseline remains unchanged. Frozen source, raw states, client histories and
controller-validation artifacts stay in ignored local directories.

The rebuilt manuscript has 5,265 main-text words. Its reported Flesch-Kincaid
grade is 10.9 and reading ease is 38. The scaffold verification gate passed,
including formatting, declarations, provenance and PDF/Word freshness.
