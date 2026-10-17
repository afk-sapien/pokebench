# Healing completion and matched interface pilot

Protocol: red-v0.47-healing-completion. Package: 0.33.0.

Healing completion now requires actual full HP and cleared status for the original
party at the required location, outside battle, without a blackout. It does not
require menu cleanup. Existing valid-state and two-confirmation checks remain.
Historical runs keep their original evaluator and result files.

## Matched design

Eight new trials compare the frozen v0.45 interface plus its reviewed Claude v4
response adapter against the revised v0.46 interface. Both arms use the corrected
healing predicate. The before snapshot also receives the same 8192-token Claude
output allowance as the after arm. These common adjustments prevent scoring and
output headroom from confounding the interface comparison.

The two tasks are starter from outside Oak's lab and party recovery in Lance's
room. Sol and Sonnet 5 each receive the same registered variant-01 state, full
observations, medium effort, 150,000 total token ceiling, 30-call maximum and
900-second maximum. Both arms use eight-turn segments and a 12,000 context threshold.
Core 0.1.4 and PyBoy 2.7.0 remain fixed. The shared empty-storage read repair is
applied to both arms. No observation slimming or paid compaction is introduced.
Arm order is counterbalanced across task/model pairs. At most one trial per
provider runs at a time. Sampling is not fixed and timing is not a primary metric.

All trials, source snapshots, explicit baseline patches, scenario hashes, usage
and replay proofs are stored in the private artifact directory
`data/matched-interface-v047`. A two-million-token conservative reservation sits
within the existing 300-million-token authorization. Actual caps total 1.2 million.
No scored main-leaderboard trial is replaced.

## Fresh results

| Task | Model | Before, reported tokens | After, reported tokens |
| --- | --- | --- | --- |
| starter | Sol | token_budget (137,916) | token_budget (136,774) |
| starter | Sonnet 5 | token_budget (131,286) | token_budget (134,076) |
| item-recovery | Sol | Pass (84,287) | Pass (54,357) |
| item-recovery | Sonnet 5 | Pass (95,892) | token_budget (119,320) |

All eight traces replay correctly. Reported usage totals 893,908 tokens.
Sol healing improved in this sample, while Sonnet healing passed before and
failed after. The failed after run repeatedly encountered unsupported menus
and no-active-menu responses. This is remaining controller and recovery friction,
not a structured response failure. No broad improvement is established.
One run per cell does not establish a win rate or prove improvement. Budget stops
are admission decisions with headroom, not literal consumption of the whole cap.

## Offline scoring evidence

Two old healing traces were replayed frame by frame with both predicates.
Their original evidence, screenshots, action hash chains and awards were verified.
Under the corrected predicate, Sol completes at call 6 and avoids three later
calls totaling 35,205 tokens. Sonnet completes at call 9 and becomes a pass,
avoiding one later call totaling 17,041 tokens. These are counterfactual scores
on recorded actions, not fresh samples. The original result files are unchanged.

## Token evidence and limits

The previous four-trial smoke used 474,317 reported tokens. Input accounts for
97.7%, and 65.3% of input is cached. Cache reads and writes are included once in
input totals. Cached processing is not the same as new generated reasoning.

Whole-party replacements occupy 49,772 of 94,109 observation bytes for Sol healing
and 56,883 of 110,952 for Sonnet healing. HP/status changes resend unchanged move
metadata. Healing rotated through four and six segments respectively, compared
with two and three on starter. There are no paid summarization calls.

The budget guard uses conservative UTF-8 byte estimates plus image and output
allowances. Sonnet starter stopped with 18,287 tokens left, less than the next
call's estimated minimum. Providers do not expose exact image/schema/prompt/history
token attribution. Byte counts must not be presented as token counts.

The next isolated optimization should be per-party-slot field deltas, with full
snapshots at segment boundaries. This preserves the same available information.
It is a recommendation from this audit, not a change included in this comparison.

Reproduction scripts and detailed per-call data are saved with the artifacts:
`run.py`, `replay_scoring.py`, `usage_audit.py`, `report.py`, `pilot.json`,
`healing-counterfactual.json`, `token-audit.json` and `analysis.json`.

Local report: http://127.0.0.1:8942/matched-interface-v047.html
Local replay: http://127.0.0.1:8942/matched-interface-v047-review.html
