# Lorelei tactical battle

This deliberately curated battle tests decisions with a small, underleveled
party. It is a synthetic team on an authentic Pokemon Red battle checkpoint,
not an archived natural-play party. The original game rules and opponent are
unchanged. Team and bag edits happen only during offline construction before
battle. Trials use controller actions only.

| Pokemon | Level | Moves |
| --- | --- | --- |
| Poliwrath | 50 | Hypnosis, Amnesia, Surf, Rest |
| Pikachu | 45 | ThunderShock, Thunder Wave, Quick Attack, Agility |
| Haunter | 45 | Hypnosis, Dream Eater, Night Shade, Confuse Ray |

The bag contains one Elixer. No Revives or HP healing items are provided.
Pokemon start healthy with full PP. DVs are fixed at 8 for Attack, Defense,
Speed and Special, with the derived HP DV of 0. Stat experience starts at zero.
Moves are legal through level-up or Red TMs/HMs. This controlled low-training
team is intentional. No strategy or opponent future moves are given to agents.

## Luck and repeats

`red-tactics-v2` registers one task with five timing variants, not five separate
benchmarks. Each starts at the same first battle menu with the same team and
opponent. Fixed waits of 0, 17, 37, 67 and 97 released-button frames yield five
checksum-pinned states. No RNG memory is patched or favorable variants selected.
These are reproducible timing variants, not a claim of independent random seeds.
Player action timing also affects battle randomness.

Run the suite with `--repeats 5`, or a multiple of five. Every model gets the
same variants in the same cycle, with a fresh context and 500,000 tokens per
attempt. Five attempts cost at most 2.5 million tokens per model. Score is wins
divided by attempts, never best-of-five. One task still receives one task's
weight in the aggregate leaderboard. Match variant IDs as well as repeat IDs.

A party wipe ends this new objective immediately as `battle_loss`. Walking back
or reloading is not a retry mechanism. Infrastructure failures remain separate
from gameplay losses. Old milestone tasks retain their original semantics:
those runs could continue after a blackout if their remaining budget allowed it.
Old single-run results do not establish a battle win probability.

Five trials are a pilot reliability check, not a precise win-rate estimate.
Publish all outcomes, consumed tokens and costs. Expand the preregistered trial
set before making strong model rankings. A separate adaptation benchmark could
allow learning across retries, but it must have its own shared total budget and
score. Do not silently mix that protocol into this task.

## Curation and validation

`scripts/prepare_tactical_fixture.py` builds local states and records offline
reference policies through the same controller-command interface used by models.
Calibration traces are not model results and never enter model rankings.
Successful references and idle negative controls must replay exactly before
suite registration. Earlier calibration outcomes are preserved. A stronger
reference policy is evidence of a possible win, not a guaranteed optimal policy
or proof that all damage-only strategies fail.

The new single-attempt objective and starting-variant protocol are recorded as
`red-v0.41-experimental`. Existing frozen batches keep their earlier source,
saves, objectives, scores and budgets. Private ROMs, states, generated catalogs
and run traces remain local and are not committed.

## Historical initial calibration

The fixed v2 tactical policy won 2/5 variants. The damage-only policy won 0/5
(4 battle losses and one policy limit). This is a small offline calibration,
not a model evaluation or proof that every damage-only policy must lose.

Winning controller references were subsequently found for every fixed variant.
Variants 2 and 3 use a lower recovery threshold. Variant 5 extends the preserved
first reference attempt by using Night Shade after Dream Eater exhausts its PP.
The full composed trace replays from the original start, with no mid-battle
state edits or rollback. Reference selection proves feasibility, not a 100%
win rate. All original failed and limited attempts remain preserved locally.


## Reliability revision

Benchmark `red-v0.42-experimental` introduces the revised team as
`red-tactics-v2`, with the 27-task catalog `red-ability-v6`. The original
`red-tactics-v1` retains Poliwhirl at level 45 and Pikachu with Thunderbolt.
No historical checkpoint or model result is rewritten.

The old calibration had implementation defects, including repeated requests
for an exhausted move. Its selected winning references established feasibility
only. They do not establish a 5/5 success rate for one policy. The replacement
reference checks PP and inventory, tracks only confirmed stat boosts, and
receives the same public observations and command dialogue as model agents.
It cannot access the emulator, enemy memory, evaluator flags or RNG state.

The tactical reference is frozen across starts. A basic attack policy and a
stronger attacker using type matchups, STAB and switching run from identical
starts. Neither is claimed to be the best possible attack strategy. Both can
use the supplied PP item. Fallback status moves can occur after all attacks
are exhausted, so these are attack-focused baselines rather than a proof about
all damage-only play.

Before testing the first holdout, acceptance was fixed at:

- At least 29 tactical wins out of 32 timing variants.
- At least 13 more tactical wins than each attacking baseline.
- Zero invalid actions and all registered trials present exactly once.
- Every controller trace replays and every policy and starting-state hash matches.

The first holdout used a level 50 Poliwrath while retaining Thunderbolt on
Pikachu. It yielded 32/32 tactical wins, 4/32 basic attacking wins and 22/32
type-aware attacking wins. This failed the separation criterion. It remains
experimental. The second candidate replaces Thunderbolt with ThunderShock,
retains the same tactical policy, and uses a fresh set of 32 offsets that
excludes every first-holdout offset. Development trials and both holdouts are
preserved. Candidate changes never rewrite earlier results or relax the gate.

### Reproduce offline calibration

Run in the benchmark checkout with a private ROM, game catalog and verified
League entrance fixture. Each output directory must be new:

```sh
PYTHONPATH=src:scripts .venv/bin/python scripts/calibrate_tactical.py \
  --rom /path/to/pokered.gb --game-data /path/to/game-data \
  --source data/red-ability-v4/fixtures/league \
  --output data/tactical-validation/new-holdout \
  --candidate wrath50-thundershock --split holdout --seed 20261004 \
  --exclude-registration data/tactical-validation/wrath50-holdout/preregistration.json
```

The original executed policy source is preserved as `frozen-policy.py` in each
calibration directory. Use that copy to reproduce an exact historical policy.
The current CLI adds explicit candidate and sampling arguments with the same
policy behavior. No model calls are used for calibration.

`scripts/report_tactical_calibration.py` validates complete evidence and
publishes a readable HTML report plus JSON. A validation result applies only
to the exact registered fixture version. Experimental fixtures remain visible
but cannot affect model rankings, including the combined analysis.

Timing variants are not established independent random samples. We therefore
do not attach a binomial confidence interval or claim a perfect underlying
win probability. Passing demonstrates observed robustness and a clear policy
contrast on the fixed tests. It does not prove optimal play or eliminate luck
from individual model trials. Five shared model trials remain a pilot, with
all five outcomes reported rather than a best-of score. Increase the shared
trial set before interpreting small differences between models.


### Revised-team holdout results

The revised team passed: tactical 31/32, basic attacking 0/32, and type-aware attacking 0/32. All 96 trials replayed, with zero invalid actions and 32 distinct tactical trajectories. The same frozen tactical policy also won all five published pilot variants. No paid model trials were started for this validation. Full calibration results and every original trace remain local. The portal links the calibration report from the tactical benchmark detail.

The sole held-out loss was start 031. Paralysis, confusion and a critical hit
contributed, while the fixed policy delayed status recovery. A separate
post-hoc diagnostic used Rest below 80 percent HP when paralyzed and won from
that state. It is preserved in `data/tactical-validation/posthoc-risk-diagnostic`
and excluded from calibration scoring. The registered result remains 31/32.
This does not prove an unavoidable loss, a perfect replacement policy, or a
clean causal separation between luck and decisions. Different actions also
change the random sequence.
