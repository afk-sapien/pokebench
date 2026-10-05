# Parcel collection and return pilot v024

Run Sol (`gpt-5.6-sol`) once from `parcel-roundtrip-v024`. This checkpoint is
imported from the verified final state of `navigation-starter-v023-sol-250k-01`,
with one declared rendering frame. It begins in Oak's lab with Charmander,
without Oak's Parcel or a Pokedex. The rival encounter has not been skipped.
There is no prepared roundtrip reference solution yet. This is a new segment,
not another starter attempt or a claim of full-game progress from one session.

The player-facing objective asks the model to collect Oak's Parcel from the
Poke Mart in Viridian City, return it to Professor Oak in Pallet Town, and
complete the handover to receive the Pokedex. It supplies no route, coordinates,
map destinations, battle strategy or reference controls. Keep default names.

Use subscription client 0.157.0, medium effort, the unchanged v023 gameplay
observation and command interface, and fresh decisions with bounded notes and
observed map memory. Freeze runtime source before dispatch. Package 0.16.0 and
benchmark red-v0.24-experimental add the separate parcel-roundtrip scorer.
The old delivery-only objective still starts with the parcel already held.

Reserve 250000 reported input plus output tokens for one attempt. Allow at most
100 calls, 1500 raw actions, 120000 game frames, 1800 wall seconds, 600 frames
per requested action phase, 7200 per dialogue phase and 2048 notebook bytes.
The larger raw-action ceiling accommodates battles and both travel legs.
No automatic retry, reset credit, model substitution or budget extension.
A reservation before the next call can stop the attempt below its token cap.

The private evaluator must observe parcel acquisition in a valid state during
this run. Completion then requires the delivered-parcel flag, removal of the
parcel from the bag, a Pokedex, and no battle, confirmed for two frames.
These evaluator facts are not supplied to the model. Record pickup as diagnostic
progress, not a separate completion. Blackouts are not automatic failures if
ordinary game recovery still allows completion within the same budget.

Verify paired model text/image delivery, complete token accounting, source and
fixture checksums, and deterministic controller replay. Publish the review and
sanitized findings regardless of outcome. Preserve earlier results separately.
