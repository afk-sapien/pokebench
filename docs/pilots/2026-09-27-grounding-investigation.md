# Screen interpretation and repeated-plan investigation

The image pipeline works, but neither model reliably translates the images into
navigation decisions. This investigation did not demonstrate improved starter
completion. More tokens and a richer notebook alone have not solved the problem.

## Evidence

Read-only perception probes used saved game images without advancing the game.
Terra at low effort and Luna at medium effort identified a bed-like object and
reported no visible stairs on the starting screen. Terra at medium effort
misidentified that same screen. Another Terra probe distinguished indoor and
outdoor panels. This supports image delivery, not reliable perception.

Gameplay remained prone to describing the bed as stairs. One previous Luna run
revisited an identical PNG 34 times while its notebook retained at most two
unsuccessful attempts. A scrolling camera also makes player screen position a
poor movement signal. The viewport does not show the entire room.

High-effort probes on two saved gameplay decisions did not rescue their plans.
Terra still chose the lower-left furnishing, and Luna still treated that area as
a possible staircase. These isolated probes do not estimate an effort effect.

## Version 0.6 validation

The optional `grounded` policy asks for a visible-scene assessment before one
controller plan. It removes the separate next-action field from model memory,
keeps durable exact-image visit counts and unchanged-input history, and explains
scrolling viewports and explicit transition waits. It supplies no route or RAM
facts on the visual track. The exact runtime source is archived locally under
`data/source-snapshots/c6c7661a50204da01352f93ceb36e781d22aec6585b5ab3e8376ac51dbb05383`.

Both trials used the verified starter checkpoint, visual observations, low
reasoning effort, and a 100,000 reported-token threshold. Other bounds were
40 calls, 320 actions, 100,000 emulator frames, 1,200 wall seconds, 600 frames per
action, and two actions per decision. Token reservation ended both runs below
the threshold. Neither left the bedroom or obtained a starter.

| Model | Reported tokens | Calls | Actions | Frames | Wall seconds | Completed |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Luna | 94,177 | 14 | 16 | 442 | 136.83 | 0/1 |
| Terra | 92,105 | 13 | 13 | 584 | 190.16 | 0/1 |

Both complete controller traces passed deterministic replay. Luna trace head:
`5005f98d9abd45e07c85ea2a3a9fb41e632d8311a929329a741c0d4161a7320c`.
Terra trace head:
`0e9768993e9746d71df08028bdb486b0e694e9d7225a27005ea40a398b2ce908`.
Run IDs are `starter-v06-luna-100k-01` and `starter-v06-terra-100k-01`.
These smaller-budget trials are not matched comparisons to the earlier 500k runs.

The four neutral probes used 22,063 tokens. The two high-effort probes used
12,346. Gameplay validation used 186,282. Total reported usage for this
investigation was 220,691 tokens. Diagnostic calls are excluded from game results.
These counts include cached input once and are not subscription-credit estimates.
Raw probes and offline checks remain in the ignored local directory
`data/grounding-investigation-2026-09-27/`.

## Version 0.7 implementation

`--codex-policy grounded-motion` adds two opt-in changes to the grounded policy:

- A conservative estimate of background translation from consecutive images.
  Positive dx means the background shifted right, and positive dy means down.
  Ambiguous alignment returns null. This is not a player coordinate or proof of
  collision. It never selects a controller action.
- A `--max-stagnant-decisions` budget, default 12. Before another model call,
  stop if this many consecutive decisions produced no previously unseen PNG.
  The stop reason is `observation_stagnation_budget`. This protects spending
  during repeated views, rather than proving lack of task progress. Animation
  can defeat it, and necessary revisits can trigger it. It is recorded in limits
  and agent metadata, so affected runs remain distinct comparison groups.

Offline motion checks covered 250 recorded actions. Of 244 same-map pairs, the
estimator returned 230 estimates. Of those, 220 agreed with a coarse translation
proxy from private tile-coordinate deltas. The other 10 often involved partial
scrolling, where the tile proxy is not pixel ground truth. Do not interpret these
counts as detection accuracy. Private coordinates were used only for offline
checking and are not inputs to the estimator or the visual agent.

The `pixel_labels` module is an offline assisted-vision prototype. It locates
complete exact pixel patches and attaches a supplied human object label. It
records template and screenshot hashes. It reads neither maps nor game memory.
A private bed template matched all 13 saved current views in the Terra trial.
This is a narrow same-scene check, not validation of a general object detector.
Occlusion, palette changes, unseen sprites, and new objects are unsupported.
No sprite data ships in the repository. No object labels reach live agents yet.
Any future assisted track must hash its annotation bank in the comparison group
and report results separately from screenshot-only play.

The new motion policy and spending guard pass synthetic and runner tests. They
have not been validated by a new model gameplay trial. The baseline `standard`
policy remains the default. No scoring or controller timing changed.

## Scope correction and next experiment

The user clarified that perception is part of the skill being benchmarked.
The proposed live object-label direction is shelved. The prototype remains an
unused offline diagnostic, not a planned baseline feature. Test Sol with the
exact archived assessment-first protocol and the same 100k budget instead.
A failed unassisted attempt remains a benchmark result.

If broader model evidence establishes a common bottleneck, consider a limited,
predeclared hint experiment. Record hint text, trigger, timing, and count, keep
the unassisted outcome, and report assisted outcomes separately. No hint is
provided in the current trials and no hint mechanism has been implemented.

Curate independent checkpoints for obtaining a starter, delivering the parcel,
and catching a first Pokemon. Successful reference replays are required. This
prevents a single bedroom-navigation failure from hiding dialogue, battle, or
resource-management competence. Keep whole-game endurance as a separate task.


The subsequent [matched Sol trial](2026-09-27-sol-matched-v06.md) also failed
within its 100k threshold. Sol did correct its interpretation and identify the
visible staircase before budget reservation stopped it. This follow-up used
92,051 additional tokens and received no hints or object labels.
