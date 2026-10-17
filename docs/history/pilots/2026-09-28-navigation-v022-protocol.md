# Autonomous navigation repair cycle v022

Declared before model calls. This development cycle tests framework corrections,
not model tuning toward a hidden route. Preserve every attempt and freeze source
for each batch. Changes apply only to the assisted gameplay track.

The first batch runs Luna, Terra, Sol and Astra once each from starter-v010.
Use the subscription client 0.157.0, medium effort and 250000 reported tokens per
attempt. Retain the same 100 model calls, 600 raw actions, 120000 frames, 1800
wall seconds, 2048-byte notebook and 600-frame action phase as v021. Dialogue
settling remains capped at 7200 frames. Use a 12000-token context threshold.

New controller behavior reports partial movement and before/after positions,
waits through observed map transitions and controller locks, and accepts up to
eight explicit straight-line tiles. It never selects a direction or destination.
The observation automatically includes a bounded map assembled only from already
observed terrain and the last eight movement results. The prompt is shorter.
No route hints, unseen terrain, save edits or evaluator facts reach models.

Allocate at most 2000000 reported tokens for this repair cycle. The first batch
reserves 1000000. Remaining allocation can test corrections identified from
these results, with new frozen source and a declared batch configuration before
calls. Do not repeat unchanged attempts merely to obtain a pass. No campaign
attempt, account reset or model substitution is included.

The service does not offer a hard aggregate generation cap. Reserve the estimated
next call before dispatch. Stop admitting further batches after incomplete
accounting or an allocation overrun. All calls, including summaries, count.
Offline emulator probes and tests do not call models and do not change fixtures.

Verify model-input delivery, budgets and deterministic controller replay.
Engineering outcomes and final comparisons must remain distinguishable. A failure
is preserved even if a later framework revision succeeds. Old versions are not
rescored. The purpose is to remove demonstrated interface obstacles while leaving
perception, exploration and strategic decisions with the tested model.
