# Sol parcel roundtrip pilot v024

Sol did not collect or deliver Oak's Parcel within the declared 250,000-token
cap. It used 245,291 reported tokens across 39 decisions and stopped through
next-call token reservation. It remained on Route 1 at x14, y5, outside battle.
It had no parcel or Pokedex. This is one failed attempt at the longer task,
not evidence that the parcel task is impossible or that Sol can never finish it.

The checkpoint continues from Sol's verified v023 starter acquisition. It has
Charmander, an unfinished rival encounter, no parcel, and no Pokedex. One setup
frame renders the imported state. The player-facing objective names Viridian's
Poke Mart and Professor Oak as the collection and delivery locations. No route,
coordinates, reference action sequence or hidden evaluator fact is supplied.

The model lost the rival battle and continued through the game's normal recovery.
It left the laboratory, crossed Pallet Town, and navigated north on Route 1.
Wild encounters and route exploration consumed additional decisions. It won a
later wild battle and Charmander reached level six. The budget stopped the run
before it entered Viridian City. The stopping observation was ordinary overworld
control, not a dialogue or menu deadlock.

Of the model calls, 13 began with a battle observation and used 78,673 reported
tokens. The other 26 calls used 166,618. This partition classifies the input
observation, not the entire controller action or its later automatic dialogue.
The run executed 437 raw actions and 13,160 game frames. No model summary calls,
retries, account reset or budget extension occurred. Subscription token reporting
is not converted into an invented API dollar charge.

The new private scorer requires a parcel pickup during this attempt before
accepting delivery. Completion also requires removal from the bag, the game's
delivery flag, a Pokedex and battle exit, confirmed for two frames. The existing
`parcel` objective remains a separate delivery-only task with the parcel already
in the starting inventory. The roundtrip fixture's source was verified, but no
successful full roundtrip reference has yet been recorded.

All 39 exact text/image pairs were verified together in actual client messages.
Usage reconciled with the run total, and the entire raw-controller trace passed
deterministic replay with matching screenshots and evaluator evidence. The new
scorer also has tests for incompatible starts, missing pickup, incomplete delivery,
battle state, two-frame confirmation and pickup persistence through recovery.
The repository suite passed 192 tests with two optional emulator checks skipped.
Lint passed.

The next comparison should preserve this outcome and explicitly declare a
larger allowance or a separately curated collection-only/return-only segment.
This trial does not justify silently extending an exhausted run or counting a
partial journey as completion. No further model calls were made in this pilot.

[Watch the attempt](http://127.0.0.1:8942/parcel-v024-review.html).
The declared protocol is `2026-09-28-parcel-v024-protocol.md`. The sanitized audit
is `paper/analysis/inputs/parcel-v024-audit.json`. Frozen source, raw states,
controller logs and client histories remain local in ignored directories.

The rebuilt manuscript has 5,486 main-text words. Its reported Flesch-Kincaid
grade is 10.9 and reading ease is 38. The scaffold verification gate passed.
