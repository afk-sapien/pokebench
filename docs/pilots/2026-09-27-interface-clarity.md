# Current-view and previous-plan clarification

The saved million-token runs used red-v0.6, not the later compact interface.
Their deterministic replays and image hashes passed. Sol reached starter selection
and the nickname prompt. Luna remained in the house, while Terra reached town and
returned home. This supports a model-capability difference on these particular
attempts, but one trial each cannot isolate model quality from interface effects.

## Observed failure evidence

Luna decision 99 described outdoor signs, trees, and buildings. Its saved input at
frames 3936 and 3960 visibly shows bedroom furnishings. The evaluator independently
records map 38. This is a mistaken interpretation, not a missing screenshot.

Terra decision 136 described a fully black current screen. The supplied strip's
left panel at frame 7540 is black, but the right, current panel at frame 7600 shows
a furnished room. At decision 138, both panels visibly show the same room, yet
Terra again calls the current view entirely black. Temporal confusion is one
plausible explanation for decision 136, but does not explain decision 138 by
itself. Persistent mistaken memory or visual interpretation may also contribute.
These are observations and hypotheses, not measured causal attributions.

Each stateless request receives notebook text and controller results. The prior
plan's expected visible result was saved in the run log but not supplied to the
next call. Grounded and compact policies also remove the obsolete next_experiment
notebook field. Consequently useful intent can disappear even while raw input
history remains. This is an interface omission worth addressing.

## red-v0.9-experimental changes

- The default compact policy labels panels EARLIER or CURRENT. CURRENT always
  occupies the final used panel, even when its pixels match an earlier view.
  Chronological references are remapped without dropping any distinct pixels.
  The header uses the current frame number, not the frame of the first occurrence.
- Agent context explicitly names current_panel. Game pixels are untouched.
- After a controller batch actually advances the game, the runner preserves its
  model-authored intent and expected visible result, decision ID, and resulting
  frame. The next request receives this as previous_plan, clearly a prediction.
  Rejected requests cannot replace the last executed plan.
- Assessment includes a short previous_result field. The model must compare the
  visible outcome with its own expectation and can report uncertainty.
- The prompt distinguishes black regions from a completely blank screen without
  identifying room types, objects, routes, or player coordinates.
- Compact history now accepts rejected-action error entries. Previously these
  lacked the frame/action fields expected by the compactor and could cause a
  context-building exception on the retry. This defect affected compact mode,
  not the older v0.6 trials analyzed here.

There are no automatic inputs, extra emulator ticks, object labels, motion
estimates, route hints, new stopping guards, or scoring changes. The no-nicknames
rule remains. New harness, prompt, memory protocol, and benchmark identifiers
separate these observations from earlier results. Previous results are preserved.

## Validation and next measurement

Synthetic tests check exact native-pixel preservation, the A/B/A duplicate case,
current-panel references, notebook persistence, review compatibility, and recovery
from an invalid action without losing the last executed plan. No live model calls
were made for this change, so improved game completion is not yet demonstrated.

The next useful experiment is a bounded matched comparison on the same starter
checkpoint with Luna and Terra, keeping effort and budgets identical. A small
saved-screen diagnostic should also check whether Terra now describes the current
room rather than the earlier black panel. Run each diagnostic in a fresh context,
keep it separate from gameplay scores, and predeclare its token budget. Do not
increase to another million-token run until the interface is validated.

Repackaging all 433 saved inputs retained the previous 58–59% image-patch reduction.
With previous-plan text restored, serialized context is 29–32% smaller than v0.6,
compared with 39–43% for v0.8's more aggressive omission. The new prompt is 2,304
UTF-8 bytes versus the recorded v0.6 prompt's 1,903. These are offline size checks,
not model token measurements. The extra text is an explicit tradeoff for continuity.
The v0.8.1 comparison implementation is preserved at commit `6832d07`.
