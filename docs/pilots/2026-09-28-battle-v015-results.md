# Battle-only pilot results

All four models began at the same battle command menu with the same image,
controller protocol, medium reasoning effort, CLI 0.157.0 and 100,000-token cap.
The matchup was a full-health level 6 Squirtle against a level 3 Rattata.

| Model | Verified completion | Decisions | Actions | Reported tokens | Final state |
| --- | --- | --- | --- | --- | --- |
| Luna | No | 13 | 25 | 91,980 | Rattata still had 5 HP, Squirtle had 15 HP |
| Terra | No | 12 | 14 | 93,089 | Rattata fainted, victory dialogue remained |
| Sol | Yes | 12 | 21 | 96,418 | Battle exited, 24 experience earned |
| Astra | Yes | 7 | 9 | 47,930 | Battle exited, 24 experience earned |

The total was 329,417 reported tokens, including cached input, with complete
accounting. Luna and Terra stopped at the prospective token reserve rather than
overspending the cap. No retries or additional model calls were made.

All four traces replayed successfully. Every recorded input image hash was found
in its actual Codex client conversation. Settings matched across models except
model identity. A real escape control received zero credit and replayed. The
wild fixture rebuilt byte-for-byte from its 120-action curation record, and its
reference victory replayed independently.

The battle trial narrows the earlier failure diagnosis. All four models selected
Tackle. Luna repeatedly requested short 60-frame waits and spent most of its
calls moving through animation and dialogue. Terra defeated the opponent but
ran out of budget before receiving experience and exiting. Astra used longer
240- and 480-frame releases or waits, which reduced calls spent on transient
screens. Sol used 120- to 240-frame waits and finished close to its token cap.
Different controller timing can change the game's random outcomes, even from
identical initial save bytes.

These traces support investigating controller timing and token overhead, rather
than describing every incomplete run as failure to understand battle strategy.
They do not prove that a new timing prompt will improve every model. A future
controlled timing comparison should keep this baseline intact and declare its
changes before new calls. The current suggestions were not changed for this batch.
One attempt per model does not estimate success rates.

PokeSim is the offline generator for subsequent gym fixtures. Curation has access
to privileged diagnostics and is not scored. That access remains unavailable to
model participants. The gym checkpoint is a separate task and does not change
these fixed wild-battle results.


## PokeSim-generated gym fixtures

The story-focused curation run reached Brock in 4,513 controller actions and
115,448 frames, taking 16.67 local wall seconds and no model calls. Optional
collection projects were deferred. The earlier default-policy attempt spent
446.59 seconds on collecting and training before it was stopped. Its private
trace and final state were retained. No memory values or sibling saves were changed.

The entrance checkpoint has state hash
`e137251536c4125903e4d5469a9173298c9c74c79883d0cf2f5fbf2edcb229f0`. Its reference earns the badge in 1,581 actions and 41,079 frames.
The battle-menu checkpoint has state hash
`79b416afdafa7af103f0fd739f9dbdcb92a51fe8b6a8f079c66f3a9dd0262d18`.
Its reference earns the badge in 858 actions and 24,231 frames. The starting lead
is a level 12 Squirtle at 8/34 HP with five other party members, so this is a
wounded-party scenario. It is not part of the four-model wild-battle results.

PokeSim curation and reference generation used core 0.1.2 and PyBoy 2.7.0.
The benchmark runtime remains on core 0.1.1. Replaying the entire curation trace
under core 0.1.1 reproduced both save states and previews byte-for-byte, and both
victory references replayed there too. These checks avoid silently assuming
cross-version checkpoint compatibility.
