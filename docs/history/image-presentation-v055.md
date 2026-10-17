# Screenshot presentation comparison v0.55

Current-only screenshot input was already the default for both bounded Codex and
Claude gameplay runs. The v0.53 and v0.54 pilot manifests record
`presentation: current`, and their ordinary decision artifacts contain one screen.
The human replay independently displayed decision-start and action-result images.
That pair was not evidence that both images were sent to the model. The earlier
recommendation to implement current-only input overlooked the existing behavior.

## Actual change

Current-only remains the default. An explicit `before-after` experiment selects
the previous decision boundary and current boundary, excluding intermediate
controller frames. The first decision has one image. Both conditions preserve
Gen 1 pixels at the same 3x nearest-neighbor scale. The experimental pair labels
the earlier panel PREVIOUS DECISION and the latest panel CURRENT. No future result
is supplied before the model chooses its action.

The existing factual last-command result, text observations, retained conversation,
notebook and on-demand screenshot recall remain available. Current-only refers to
new ordinary screenshot input. Earlier turns can still contain images in the
retained conversation. Explicit look-back can add earlier screenshot input.

The existing `--presentation` option accepts `current` or `before-after` for bounded
gameplay runs, including Claude. `catalog-run` now exposes the same option and
records it in the provider configuration. Preparation is text-only and rejects
this gameplay image experiment. Existing strips remain a separate legacy visual
condition and are not used as the matched pair, because their scale differs.

Replay pages keep the human side-by-side view. Its labels now say DECISION START
and ACTION RESULT. A separate panel shows the recorded screenshot actually sent
to the model and lists any explicitly requested historical frames. These display
changes apply when exporting older runs without changing their saved observations.

## Matched pilot

The private artifact root is `data/image-comparison-v055` in the private benchmark
artifact checkout. It contains two models, Sol and Claude Sonnet 5.5, and three
tasks, each run once per screenshot condition:

| Task | Per-attempt token ceiling |
| --- | ---: |
| Manual Potion healing | 200,000 |
| Brock with the prepared team | 75,000 |
| Saffron Gym warp navigation | 300,000 |

The combined ceiling is 2,300,000 reported input plus output tokens. A transport
checks usage between responses and cannot hard-cap an already in-flight response.
The same native save, task, action rules, prompt, low effort, screenshot scale and
budget are used within each pair. Condition order alternates across tasks and
models. Each attempt gets a fresh model session. No automatic paid retries occur.

Report completion, tokens, model calls, image panels and mean reported input per
call. Total token differences can reflect different decisions, context rotation,
cache behavior and early success, so they are not a direct measure of image token
cost. One attempt per condition cannot establish statistical equivalence or a
reliable model ranking. This comparison does not justify discarding older results.

The protocol is `red-v0.55-image-comparison`. No task scoring predicate, game state,
Core controller, shortcut policy or default screenshot condition changed.

## Completed results

All twelve attempts completed with known usage and no recorded infrastructure
failures. Both conditions passed healing and Brock for both models. All four
navigation attempts reached the 300,000-token cap. Current-only used 868,363 tokens
over 89 calls. Before/after used 866,048 tokens over 86 calls. Combined usage was
1,734,411 tokens, below the 2,300,000 ceiling. The total-token difference is below
1 percent and does not establish an image-cost saving.

All six pairs were verified to share their task prompt hash, starting-state hash,
task specification and budget. Their initial screenshot bytes were also identical.
Recorded ordinary inputs contain one panel in current-only mode and at most two
in before/after mode. Both modes retain on-demand screenshot recall.

Keep current-only as the default. No new token saving is claimed because it was
already the default. This comparison offers no clear reason to add the previous
screenshot routinely. The final local report is `image-comparison-v055.html`, with
downloadable data and all twelve replays. Seventeen earlier pilot replay pages
were also refreshed with actual model-input evidence. Historical run data did
not change. Verification passed 756 tests with three skips and the lint check.
