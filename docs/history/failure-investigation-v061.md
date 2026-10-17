# Focused failure investigation v061

Investigated on 2026-10-12. Source: focused-pass-v056 and its recorded v057/v058 replacements.

## What was checked

Reviewed the 42 attempts covering Saffron and the six all-zero tasks. Read decision records, actual agent observations, final emulator states and private completion rules. Inspected screenshots and reproduced selected actions in the native emulator. No new model calls were made. Historical scores and the running frozen stability trials were not changed.

## Confirmed repairs

- **Saffron completion feedback:** The model-facing allowlist omitted the completion bit already available in Session status. Sol identified an ordinary trainer at (3,13) as Sabrina, declared success at decision 14 and stayed at (3,14) for 184 observations. The actual target is (9,9). Of 124 empty-action rejections, 112 occurred in Saffron. Future gameplay observations now explicitly say `task_status: not_complete` until success, and the shared OpenAI/Claude prompt explains automatic termination. Target identity, coordinates and intermediate grading flags remain private. This is a feedback repair, not proof of improved model performance.
- **Boulder feedback:** At Opus decision 13, the player stayed at (5,14) while the boulder moved from (5,15) to (5,16). The old feedback called this blocked. New feedback reports already-visible object position changes and removes the misleading blocked marker. Native reproduction matches the original pixels and frame 994 exactly. The emulator and push behavior are unchanged. This belongs in the benchmark observation layer, not Core.
- **Navigation replay setup:** Exact replay recreated the emulator but omitted the recorded no-wild-encounters condition. The new offline Mt. Moon reference originally diverged at action 10. Reinstalling the recorded condition fixes exact replay. This changes replay verification, not existing portal screenshots or original gameplay results.

Gameplay observation policy is now `player-information-v061`. Existing frozen trials retain their original policy and source. No new model results should be described as already improved.

## Task-by-task findings

| Task | Evidence | Interpretation and remaining work |
|---|---|---|
| Saffron Gym | Opus passed in 29 decisions. Sol, Terra, Luna and Sonnet each exhausted 200 decisions. Haiku ended after 35. Several falsely believed they had arrived. | Reachable. Completion feedback was missing. Fixed for future runs. A matched small retest is still needed. |
| Mt. Moon | Every model exhausted 300 decisions while revisiting floors. New offline reference reaches Cerulean and earns the actual task score. Exact replay verifies all 317 raw controller inputs and 16,626 frames. | Feasible. Raw inputs are not model decisions, which can move multiple tiles. The route also requires choosing a fossil. No completion-rule bug found. Budget adequacy for exploration is not proved by the reference. |
| Victory Road boulder | Every model exhausted 300 decisions. Strength was available and native pushes worked. Four final saves had the first boulder at (5,14), where models reported it wedged. | Confirmed misleading push feedback, now fixed. No complete winning reference was established in this investigation. Do not yet call the remaining zero pass rate a model limit. |
| Pikachu capture | Sol and Terra saw 8 forest encounters each, Luna 3, Opus 26, Sonnet 2 and Haiku 0. Only Opus saw Pikachu, first at decision 185/200. It threw seven balls at full HP and was still fighting at cutoff. | The task mixes navigation, encounter timing and capture skill. It needs encounter-aware calibration or a separate fixed-encounter capture test. |
| Pikachu rule mismatch | Sonnet picked up a free Poke Ball at decision 53. Its bag increased from 10 to 11, and the grader immediately failed it. The agent instruction only prohibited buying more balls. | Confirmed instruction/grader mismatch. This historical failure cannot be interpreted as violating the stated no-purchase rule. The future task contract still needs correction before rerunning it. No historical score was silently changed. |
| Bicycle quest | All six exhausted 200 decisions without reaching Vermilion. A controller-only probe from the exact start exited the Bike Shop, crossed Cerulean through the robbed house and reached Route 5. Bill and the Cerulean thief prerequisites were already satisfied. | Not trapped by the starting save. The models missed the legal southbound route. This probe verifies the route out, not the entire voucher round trip or its budget. |
| Rocket Hideout | All six exhausted 600 decisions. Sonnet observed (18,15) on B3F 312 times. Opus did reach B4F at decision 402, but returned without the Lift Key. The screenshot shows spinner arrows while the text map represents them as generic walkable dots. | Both route planning and lost terrain information matter. No evidence that the game is physically softlocked. Visible spinner direction should be represented explicitly in the assisted map. A full reference and budget calibration remain outstanding. |
| League preparation | All 30 model assessment sequences lost. Many reached Lance or the Champion. The recorded reference marker only represented a completed smoke test, with 0/1 wins. Two new legal variants, Lapras lead and Snorlax lead with two purchased Revives, also won 0/5 each under fixed-battle-v3. | Not calibrated as a discriminating preparation task. This is not an optimal-play oracle. Need a demonstrated successful legal preparation under the actual grading controller or revise the setup/controller. Ten additional failures do not prove the task impossible. |

## Replays

Use the following paths under http://127.0.0.1:8942/all-results-preview/:

- Saffron false completion: `replays/focused-v056-cell-0013.html#run=cell-0013&decision=14`
- Saffron successful run: `replays/focused-v056-cell-0016.html#run=cell-0016&decision=29`
- Mt. Moon: `replays/focused-v057-cell-0010.html#run=cell-0010&decision=140`
- Boulder push feedback: `replays/focused-v057-cell-0028.html#run=cell-0028&decision=13`
- Pikachu late encounter: `replays/focused-v056-cell-0274.html#run=cell-0274&decision=185`
- Pikachu free-ball rejection: `replays/focused-v056-cell-0275.html#run=cell-0275&decision=53`
- Bicycle route confusion: `replays/focused-v056-cell-0286.html#run=cell-0286&decision=190`
- Rocket spinner loop: `replays/focused-v058-cell-0293.html#run=cell-0293&decision=100`
- Rocket arrival at B4F: `replays/focused-v058-cell-0292.html#run=cell-0292&decision=402`

Preparation has native assessment action logs and submitted plans, rather than model gameplay replays. All new offline evidence is preserved at `<private-data>/failure-investigation-v061`. These are reference checks, not additions to the model leaderboard.

## Next bounded checks

1. Correct the Pikachu task contract and separate encounter luck from capture performance.
2. Complete native references for Victory Road, the Bicycle round trip and Rocket Hideout. Calibrate preparation against a proven winning submission.
3. Represent visible special terrain accurately in the assisted map, without revealing hidden routes or targets.
4. Run a small matched Saffron/boulder retest after those focused repairs. Do not repeat the whole matrix.
