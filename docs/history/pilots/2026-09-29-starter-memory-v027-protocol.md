# Luna outside-lab starter diagnostic with working memory

Version red-v0.27 adds observed-decision-memory-v1 to the gameplay track.
Keep the last 20 executed decisions, with grouped commands, locations, facing,
actual outcomes and dialogue references. Keep up to 64 distinct observed
conversation transcripts, each clipped to 2048 UTF-8 bytes with an explicit
truncation flag. Repeated dialogue increments counts without displacing older
unique conversations. Keep 128 matching-result signatures and show up to eight
repeated results in the current map. A repeated result is not classified as
failure and no route, prerequisite or inferred speaker identity is supplied.

Default dialogue recall uses a 6000-byte encoded entry budget. Inspect memory
allows 12000 bytes. Selection prefers conversations referenced by recent
decisions, then those in the current map, then newer distinct conversations.
Report omitted entries. Notes remain a separate 2048-byte agent notebook.
History survives normal pause and resume in the existing gameplay checkpoint.
Observations and idempotent retries never create duplicate memories. The
visual track is unchanged. The gameplay prompt explains the observed memory
and asks the agent to check outcomes before repeating a plan.

Prepare starter-outside-lab-v027 by replaying the controller prefix of the
original campaign-v026-luna-10m-01 through frame 12334, immediately before its
99th decision. Verify every replayed action's hash, evidence and screenshot.
The player is in Pallet Town at (12,12), outside Oak's lab, with no Pokemon.
The prior trace has not triggered the initial Oak encounter. Import the save
with the existing declared one-frame render wait. Do not import prior notes,
map knowledge, dialogue, decisions or any explanation of the missing event.
The preparation proof and raw game artifacts remain private.

Run one fresh gpt-5.6-luna attempt using subscription client 0.157.0, medium
effort, current screenshot and fresh decisions. Objective: obtain the first
starter Pokemon, keeping its default species name. Stop on verified starter
acquisition rather than continuing the campaign. Do not tell the agent how
to unlock the choice. Preserve 10000000 reported total tokens, 1000000 tokens
in one map, and all other v026 limits. This is one targeted diagnostic, with
no automatic retries, hints, helper models or manual interventions.

Freeze the runtime. Verify actual paired text/image delivery, the working
memory delivered to the model, token accounting, area budget and controller
replay. Export the decision review and a sanitized audit when the run stops.
The new checkpoint and shorter objective differ from the old campaign, so
this is not a controlled causal estimate of the memory change. Old runs stay
unchanged. Report whether Luna encounters the absent-Oak dialogue, changes
its plan, triggers the opening event and obtains a starter.
