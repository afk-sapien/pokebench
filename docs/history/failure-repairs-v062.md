# Failure repairs v062

These changes address the focused-pass-v056 failure investigation. Old model results and frozen runtimes remain intact. This is a local exploratory repair, not a benchmark-wide rerun or a publication update.

## Implemented repairs

- The assisted map retains visible spinner directions in Rocket Hideout and Viridian Gym. It reads on-screen tile graphics only. It does not expose unseen terrain, scripted movement paths or spinner destinations. The visual-only track is unchanged.
- The Pikachu search task permits free ball pickups. A ball increase inside a native ball-selling shop is treated as a forbidden purchase. This avoids depending on whether the game's money and inventory updates occur on the same frame. Gifts still do not count as captures.
- A separate fixed Pikachu encounter measures capture decisions without requiring a rare encounter search. It starts against a level 3 Pikachu with Squirtle level 10 at 26/28 HP and ten balls. The original search-and-capture task remains available.
- Mt. Moon now allows 650 decisions and 9,750,000 tokens. Bicycle allows 1,150 decisions and 17,250,000 tokens. These conservative decision ceilings exceed twice the raw controller input count of complete native references. Movement batching can use fewer decisions. They are not estimates of the minimum number of model decisions.
- Victory Road keeps its 300-decision budget. Its complete reference required 137 raw inputs, including Strength activation and the boulder puzzle.
- The v061 fixes remain included: unfinished-task feedback, visible boulder-change receipts, and restoring navigation conditions during replay.

Observation policy is `player-information-v062`. The catalog runtime is `catalog-runtime-v062`. Budget and fixture changes have new catalog hashes. No old score is silently replaced.

## Native feasibility evidence

All of these runs used controller inputs and zero model calls. Exact replay verification passed.

| Reference | Raw inputs | Result |
| --- | ---: | --- |
| Mt. Moon to Cerulean | 317 | Complete |
| Victory Road boulder puzzle | 137 | Complete |
| Bicycle voucher and exchange | 560 | Complete |
| Fixed Pikachu capture | 82 | Complete in four gameplay commands |

Private proofs, traces and reusable scripts are in `data/failure-repairs-v062` under the private artifact repository. The fixed Pikachu state was extracted from a recorded native encounter at frame 42404. Its party, opponent and resources were not edited.

## Preparation grading

The fixed grading controller is now `fixed-battle-v4`.

- It uses owned recovery items between League fights through native menus. Maintenance happens after the previous defeated trainer's dialogue settles. It must not happen at the next checkpoint because a trainer battle can already be queued there.
- It no longer spends turns using Amnesia against a physical-type opponent when the user has no special attacks.
- It restores an exhausted important attack with an owned Elixer rather than leaving it unused while selecting weak backup moves.

This is assessment-controller behavior, not an extra ability or recommendation provided to the evaluated model. No HP, PP or bag edits occur during battles or maintenance. The existing offline assessment fixture transfer still copies the submitted party and remaining resources into each registered opponent checkpoint.

The original level-55 setup still lost in the tested legal preparation variants. That does not prove that it is impossible or that an optimal policy would lose. A separate level-60 revision now has a demonstrated winning preparation, with the same moves, cash, shop stock and initial bag.

Across the same five timing offsets, buying one Full Restore won 2/5 and no purchase won 1/5. Both assessments completed without evaluation errors. This proves feasibility under the grading controller. It does not establish statistically reliable separation between preparations. Scores remain observed win rates, not claims of optimal play. Historical level-55 scores remain unchanged.

## Focused model retest

Twelve trials are running separately in `data/repairs-v062`: Sol and Sonnet, one attempt each on Saffron Gym, Victory Road, Rocket Hideout, Mt. Moon, Bicycle and fixed Pikachu capture.

Saffron, Victory Road and Rocket retain their old starts and budgets. Cave and Bicycle test changed budgets as well as feedback. Fixed Pikachu is a new diagnostic and cannot be compared directly with the old search-and-capture score.

The phase has a 50-million-token ceiling inside the previously authorized 552-million-token combined allowance. It uses at most two workers and one per provider. The 30-minute monitor follows the new phase and checks failures without duplicating in-flight calls. The League preparation revision is calibrated offline and is not included in this paid phase.

Local results: `http://127.0.0.1:8942/all-results-preview/repairs-v062.html`.

Do not describe the repairs as model-success improvements until these runs show that. If a model still fails, inspect the new trace rather than rerunning the entire benchmark.
