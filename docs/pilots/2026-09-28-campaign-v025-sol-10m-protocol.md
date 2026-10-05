# Sol campaign with a ten-million-token allowance

Run one fresh gpt-5.6-sol attempt with 10000000 reported input-plus-output tokens,
including cached input, through subscription client 0.157.0 at medium effort.
Start from the verified starter-v010 bedroom state after names were entered,
before obtaining any Pokemon or badges. Copy its immutable state and preview
into campaign-v025 with campaign metadata, without changing emulator state.

Use the full campaign goal. Stop only on verified Champion and Hall of Fame
completion, an execution failure, or a declared limit. Starter acquisition,
parcel delivery and Brock are intermediate milestones, not terminal objectives.
Scoring remains 75 per badge, 50 per Elite Four member and 200 for Champion,
with story milestones recorded separately for zero points.

Version red-v0.25 adds an explicit public campaign objective. The gameplay
commands, information policy, dialogue handling and fresh-decision memory
policy remain unchanged from v024. Each call receives current game information,
observed exploration memory and the bounded notebook. No routes, hints,
helper models, retries, reset credits or manual interventions are authorized
by this protocol. Decline nicknames under the shared gameplay rule.

Limits: 10000000 reported tokens, 4000 model calls, 60000 raw controller actions,
4800000 frames and 72000 active wall seconds. Preserve 600 frames per requested
action phase, 7200 per dialogue phase, one command per decision and 2048 notebook
bytes. Token accounting and next-call reservation remain enforced by the runner.
The token budget is enforced between model calls and is not a backend hard cap.

Freeze and hash the source before launch. Keep the run detached from the shell,
record milestone snapshots, and refresh a read-only progress page. On termination,
export the decision review, reconcile usage, verify actual paired text/image
messages and replay the controller trace. Preserve failures and record incomplete
accounting explicitly. Report the furthest confirmed milestones and final state,
not inferred success from model notes. One sample is an exploratory result.
