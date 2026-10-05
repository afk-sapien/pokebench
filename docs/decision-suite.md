# Decision suite v1

Benchmark version: `red-v0.44-experimental`. Package version: `0.30.0`.

The six tasks are experimental candidates. Their medium and hard labels are hypotheses until repeated model trials show useful separation. They remain outside the main ability score while calibration is incomplete. Earlier results and the existing ranking remain intact.

| Task | Decision tested | Starting situation | Token ceiling |
| --- | --- | --- | --- |
| Recover from a bad matchup | Recognize a disadvantage and switch safely | Graveler leads against Lorelei, with Poliwrath and Haunter available. Nobody may faint | 500,000 |
| Capture a healthy Snorlax | Balance damage, status, survival and capture attempts | Natural full-health level 30 Snorlax encounter, Parasect and Haunter, 12 Great Balls | 500,000 |
| Rescue a damaged team | Spend scarce recovery items on useful party members | Before Lance, damaged Jynx has no Ice Beam PP, Snorlax and Jolteon are fainted. One Revive, two Max Potions, one Elixer | 750,000 |
| Limited-PP gauntlet | Allocate resources across successive opponents | Lorelei followed by Bruno, Poliwrath and Kadabra, four Surf PP, five Psychic PP, one Elixer | 1,000,000 |
| Adaptive Champion | Change tactics as opponents change | Jolteon, Vaporeon and Ninetales against the Champion, with two Full Restores | 750,000 |
| Recovery detour | Recognize a dangerous condition and choose a recovery stop | Viridian City, one poisoned Squirtle with 4 HP, no items. Reach Viridian Forest without blacking out | 1,000,000 |

## Saves and scoring

Each task has five shared timing variants from the same setup. Every model receives the same variants and token limits. A variant is one attempt, with no gameplay reset after a loss. Winning paths selected during offline curation prove feasibility only. They are not estimates of reference reliability.

A task awards one point after two confirming emulator frames. Losing the party permanently fails the attempt. The bad-matchup task also fails immediately if any party member faints. Battle tasks preserve the supplied party identities. Capture must occur in the initial encounter and add that Snorlax to the party. Fleeing, knocking it out or blacking out cannot be repaired by starting another encounter. The Champion task includes the Hall of Fame sequence. The route task requires an actual arrival, not a blackout warp.

The party and inventory are synthetic benchmark setup. Those writes happen offline before battle. Enemy teams, damage, encounter results, RNG state and game rules are not patched. The wild Snorlax encounter comes from an archived PokeSim adventure. The original adventure and simulation saves are read-only. ROMs, emulator states and generated catalogs remain local and are not distributed with the source package.

Agents use the existing gameplay observation allowlist and controller shortcuts. They see their own party, moves, PP, bag, local map, screen and dialogue. Private scoring flags and reference strategies are not included. Context, menu commands, reasoning effort and provider behavior are unchanged.

## Validation and rollout

1. Check every save against its registered party, inventory and starting situation.
2. Verify a successful controller replay and an idle negative replay for every variant.
3. Retain every reference and baseline trial, including failed development controllers. Do not report a selected winning replay as a perfect policy.
4. Run a development pilot on the first variant with Astra, Terra and Luna. Label these as one-start pilots and exclude them from ability ranking.
5. Freeze strategies and test untouched timing variants before declaring difficulty calibrated. Collect all five starts from every model before comparing reliability. Report wins, confidence intervals, tokens and cost alongside failures.
6. Promote useful tasks only after reviewing whether stronger models separate from weaker models. A universal pass or fail is a diagnostic, not an automatic reason to delete a useful control task.

The standalone package suite is `red-decisions-v1`. The expanded catalog is `red-ability-v7`. The separate `red-decisions-pilot-v1` suite uses one variant per task and cannot be substituted for the five-start suite results.

Fixture import uses the existing `suite prepare` workflow with a bindings JSON mapping each task to five scenario and successful reference paths. Preparation checks the starts, replays every proof and verifies that idling cannot complete the task. Suite reports retain exact save, source and configuration hashes.

Offline scripts:

- `scripts/build_decision_fixtures.py` constructs the six setups from local source checkpoints.
- `scripts/reference_decision_tasks.py` runs deterministic public-observation reference and baseline battle policies.
- `scripts/verify_pokesim_checkpoint.py` runs the simulation policy for offline route feasibility. This reference may inspect simulation state and is never counted as model performance.

Neither an offline controller nor a successful curated path is supplied to the evaluated models.

## Initial development sweep

The first fixed public-observation policies won 3/5 bad-matchup starts, 5/5 healthy captures, 2/5 team rescues, 4/5 PP gauntlets and 5/5 Champion battles. The direct-attack baselines won 0/5 in each battle task. Immediate ball throwing won 3/5 captures. The simulation route reference won 5/5, and skipping recovery lost 5/5. All 60 traces replayed successfully.

Some starting variants needed a later offline feasibility search to obtain a winning reference path. Those selected paths are excluded from the fixed-policy sweep totals. The initial rates show that rescue and switching need further robustness work, and capture may still be too easy for ranking. None of these development results establishes optimal play or eliminates luck. The stronger and weaker model pilots are the next test of discriminatory value.

The local pilot is capped at 18 attempts and 13,500,000 total tokens across Astra, Terra and Luna. It uses the existing medium reasoning effort, eight-turn bounded context and no paid summaries. Each task retains its registered per-attempt limit. All game outcomes count. Infrastructure errors stop the batch for inspection.
