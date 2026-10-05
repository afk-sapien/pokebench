# Dialogue collection v020

Package 0.13.0, benchmark `red-v0.20-experimental`, observation policy
`player-information-v020`, provider `codex-app-server-gameplay-v020`.
This changes the assisted gameplay track. It leaves visual observations and raw
controller behavior unchanged. Existing model results are not rescored.

## Behavior

A command now returns the decoded dialogue shown during its execution and any
subsequent continue-only conversation. Partial typing is collapsed, scrolling
pages remain in order, and printed contractions and punctuation are retained.
This is a transcript of rendered text, without a summarizing model or extra
model calls. The collector does not retrieve future script text.

Automatic continuation stops at visible menus, naming and battle choices,
settled overworld control, task completion, or a collection/run limit. The agent
can request `advance_dialogue` to continue a conversation already open. It never
chooses YES, NO, a starter, a move or a nickname automatically.

Each result includes `pages`, `stop_reason`, `frames`,
`transcript_limit_reached` and format `screen-text-pages-v1` under
`last_command.dialogue`. Frames count the collection phase. The surrounding
command records total start/end frames and raw action count. Screen pages can
share a line when the game scrolls. A stopped or truncated collection is explicit,
and the current screenshot remains available. The transcript and command retry
record are retained in decision-boundary recovery checkpoints and audit logs.

## Detection and bounds

Continue detection requires both a dialogue UI and a recognized active call to
the pinned English Red text-wait routine. The adapter reads its distinctive
home-bank instruction pattern and live CPU stack through PyBoy. Only the routine
match is cached. Stack state is checked again before each confirmation. This is
private mechanical interface detection, not an agent observation. No hooks,
ROM patches, RAM writes or future event/text reads are used. Missing or ambiguous
routine matches do not send automatic A inputs.

All progress uses ordinary controller input. A one-frame A press is released
before the next check. Passive waits use at most 30 frames per block. A brief
blank overworld frame is not sufficient to end collection. The collector waits
for 120 passive frames of a settled overworld UI. This is a bounded settling
heuristic, not an oracle that every game script has finished.

The requested action and dialogue phases have separate limits. Dialogue defaults
to 7,200 frames, also capped at 128 pages or 16,384 characters. Unknown or long
animations return after 120 unsuccessful wait checks. Global frame, raw action,
wall time and completion checks still apply. Large conversations can therefore
require another `advance_dialogue` decision. Configure the frame limit with
`--max-dialogue-frames`. The effective value is in the run manifest and gameplay
observation. Collection does not spend model tokens, but the transcript consumes
input tokens when supplied to the model. The identical last-command result is
removed from the recent-results list so the transcript is not sent twice.

The same investigation found a menu parsing bug. YES/NO choices could include
nearby battle HUD numbers, producing labels such as `YES 13`. v020 reads active
menu rows up to their right border. Both observation and exact-choice execution
use those labels. This is an additional v020 interface change, so a later success
rate difference cannot be attributed to dialogue batching alone.

## Offline validation on 2026-09-28

These checks copied existing private states. They did not call any model or
alter the original runs. All six resulting controller traces replayed with
matching screenshots, evaluator evidence and final scores.

| Starting point | Result of one command | Total frames | Raw actions |
| --- | --- | ---: | ---: |
| Terra v019 Brock final state | Remaining reward text completes, badge awarded | 1,576 | 69 |
| Sol v019 Brock final state | Remaining reward text completes, badge awarded | 569 | 27 |
| Astra v019 Brock final state | Remaining reward text completes, badge awarded | 782 | 36 |
| Sol v019 starter final state | Oak and rival text collected, control returned, no starter selected | 1,010 | 43 |
| Brock battle fixture, explicit Bubble selection | Geodude defeated, stops at switch YES/NO before Onix | 1,066 | 37 |
| Reconstructed Luna v019 switch prompt | `advance_dialogue` leaves the choice untouched | 0 | 0 |

The three reward checks demonstrate avoidable continuation overhead in the old
harness. They do not turn the old failed model runs into new model successes.
The battle check explicitly supplied a move for controller validation. It is
not an autonomous model performance result. Private transcripts and traces are
stored under `data/dialogue-v020/` and are excluded from Git.

Unit coverage includes read-only wait detection, unsupported adapters, duplicate
routine matches, live versus stale stack entries, transcript typing and size
limits, text glyphs, all choice kinds, rejected commands, retry safety, recovery,
brief dialogue gaps, exact menu labels and global budget/completion enforcement.

## What the planning failures establish

The v019 trials used fresh model conversations for each decision. Only the
agent-authored notebook, recent controller results, current observation and
bounded exploration memory persisted. Notes were capped at 2,048 bytes. A model
could replace a useful plan with a short intent, after which earlier reasoning
was no longer in its conversation. This differs from an ongoing coding-agent
session and is a plausible harness-level contributor to repeated planning.
It does not establish that memory is the sole cause or that a particular model
can reliably play the game under a different harness.

Retained conversation and metered compaction already exist in the provider.
This change does not alter that context policy or increase model budgets. The
next comparison should hold the v020 interface, fixture, model, effort and token
budget fixed, and compare fresh decisions with retained conversation and bounded
compaction. Report planning and navigation outcomes separately from continuation
overhead. Prior visual runs with retained context are not a matched comparison
for these structured-information trials.
