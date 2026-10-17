# Sol parcel roundtrip with a million-token allowance

The user requested a 1000000-token limit after the 250000-token parcel pilot.
Run one new Sol attempt from the identical parcel-roundtrip-v024 checkpoint.
Preserve the exhausted attempt unchanged. This is a fresh attempt, not a resume
or rollback of the earlier run. Use the same frozen runtime, model gpt-5.6-sol,
medium effort, subscription client 0.157.0, objective and v023 gameplay interface.
Keep fresh decisions with bounded notes and observed map memory.

The reported input-plus-output allowance is 1000000 tokens. Increase the
supporting ceilings to 400 calls, 6000 raw actions, 480000 frames and 7200 wall
seconds so the previous call limit does not preempt the requested allowance.
Keep 600 frames per requested action phase, 7200 per dialogue phase, one command
per decision and 2048 notebook bytes. Stop automatically on completion or any
budget boundary. No extra attempts, reset credits or unmetered helper models.

Before dispatch, verify the frozen source and starting state hashes against the
previous pilot. Afterward reconcile usage, verify actual paired text/image
messages, replay all controls, and publish the review and sanitized result.
Report collection separately from confirmed delivery. Do not replace the prior
result or attribute differences solely to budget from a single new sample.
