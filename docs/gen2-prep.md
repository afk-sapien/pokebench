# Gen II preparation

This branch prepares Pokemon Crystal tasks so that adding Gen II to Short later is a small step.
Nothing in the released suite changes. The Short and Long task lists, every released
specification hash, the fixture pack and the harness source hash are the same as on main, and
`tests/test_gen2_prep.py` checks that.

## What is here

| Path | What it does |
|---|---|
| `src/pokeagent_bench/gen2/engine.py` | Crystal ROM check (SHA-256), boot with the clock locked to frames, start save and load with `initial.clock.json`, RAM facts |
| `src/pokeagent_bench/gen2/evaluator.py` | Ordered milestones, each confirmed on two different frames. Blackout ends the run. Map checks fail in battle |
| `src/pokeagent_bench/gen2/catalog.py` | Loads and validates the Gen II catalog. Pins a start and its reference |
| `src/pokeagent_bench/gen2/catalog.json` | Six hard tasks. It sits outside `catalogs/`, so `evaluation_catalog` never reads it |
| `src/pokeagent_bench/gen2/curation.py` | Drives PokeSim's Gen II story policy, which builds the starts. No model calls |
| `scripts/verify_gen2_determinism.py` | The determinism proof. Its result is `docs/gen2-determinism.json` |
| `scripts/prepare_gen2_fixtures.py` | Builds every start and scripted reference from a fresh game into the gitignored `data/` folder |
| `tests/test_gen2_prep.py` | Released suite unchanged, catalog checks, evaluator units, clock refusals, replay of every reference |
| `tests/fixtures/gen2-prep-released-specs.json` | The released suite as main had it at 1519f05 |

No ROM, save, state, clock lock, reference or pret dump is in git. All of them go to `data/`.

## Pins

| What | Pin |
|---|---|
| pret/pokecrystal | 5beda23ffa505f62e1dad7e3d7c214d1737b3358 |
| PokeSim Core | 0.12.3 |
| PokeSim | tag `pokecore-v0.12.3`, commit 37fff4cf |
| Crystal ROM | Pokemon - Crystal Version (USA, Europe) (Rev 1), SHA-1 f2f52230b536214ef7c9924f483392993e226cfb |

Every event number, map ID and source link comes from pokecrystal 5beda23f. Core's
`pokecore/gen2/mapfacts.py` and PokeSim's Gen II data bundle are both generated from that commit.
`gen2/catalog.py` holds the pin, the catalog records it, and every source link uses it. The
fixture builder refuses a data bundle or a Core generated from any other revision.

## Determinism

`docs/gen2-determinism.json` records a 120,000 frame PokeSim run from power-on, played four
ways. A second run from power-on, and two runs from a start saved at frame 60,000, matched the
first on every frame hash, work RAM hash, HRAM hash and clock reading over 3653 actions. The
clock read the same as the frame count at every step. Five refusals fired: no lock file, a lock
that does not follow frames, a lock for another state, a lock that reads before the save time,
and a ROM that is not Crystal. The record is from a rerun after the pret pin, which matched the
first run on every hash.

## Building the starts

```
PYTHONDONTWRITEBYTECODE=1 nice -n 10 .venv/bin/python scripts/prepare_gen2_fixtures.py \
  --rom /path/to/crystal.gbc --pokesim /path/to/pokesim-at-pokecore-v0.12.3 \
  --data /path/to/pokesim/data/live-soak/gen2-data --output data/gen2/fixtures
```

The story route plays 2,219,404 frames in about 140 s (15,800 fps) and the Kabuto route plays
314,510 frames in about 20 s. A start is the first settled frame on the start map with the named
events, held for two actions in a row with no battle and no script running. A capture can name a
later entry into the start map, which the Ice Path does. If the run blacks out after a capture,
that recording moves to `blackouts/` and the next qualifying entry is used, up to three entries.

Five builds were made. Builds B and C match on all six tasks. The Ice Path start then moved to the
run's second entry. On its first entry the run picks up HM07 Waterfall and walks back to Mahogany
Town, so the old reference took 1166 of its 2325 actions to come back to where the new start
begins. Build D rebuilt all six tasks and build E rebuilt the Ice Path alone. D matches C on the
other five, and D and E match on the new Ice Path start and its direct crossing.

Run the ROM tests with the built starts:

```
POKEBENCH_CRYSTAL_ROM=/path/to/crystal.gbc POKEBENCH_GEN2_FIXTURES=data/gen2/fixtures \
  nice -n 10 .venv/bin/python -m pytest tests/test_gen2_prep.py
```

## Tasks

Decision caps are five times the reference decisions. Token budgets are 15,000 per allowed
decision. Both follow the Red rule, but the decision count is a proxy until a Gen II assisted
executor exists (gap 4).

| Task | Start | Success check | Reference actions | Decisions | Cap |
|---|---|---|---|---|---|
| `gen2-ruins-kabuto-panel` | Kabuto Chamber, day, 1 badge | inner chamber map [3, 27] | 169 | 95 | 475 |
| `gen2-burned-tower-beasts` | Burned Tower 1F, day, 3 badges | event 123, beasts released | 728 | 29 | 145 |
| `gen2-rocket-hideout` | Rocket Base B1F, day, 6 badges | event 34, hideout cleared | 3557 | 179 | 895 |
| `gen2-radio-tower-basement` | Goldenrod Underground, night, 7 badges | event 74, Card Key | 2894 | 132 | 660 |
| `gen2-ice-path` | Ice Path 1F on the second entry, night, 7 badges | Blackthorn City map [5, 10] | 1159 | 296 | 1480 |
| `gen2-blackthorn-gym` | Blackthorn Gym 1F, night, 7 badges | event 1220, Clair beaten | 2199 | 165 | 825 |

The per-task test loads each start through its clock lock, replays the reference, checks the
pins, and checks that the milestones are awarded in catalog order and that success comes on the
last action and not before.

## Gaps found during the prep

1. **PokeSim pin.** The starts are built with PokeSim at tag `pokecore-v0.12.3` (37fff4cf). PokeSim's
   HEAD needs a newer Core than 0.12.3, so it cannot build these starts under this branch's lock.
2. **Milestones without the pret script.** No pokecrystal checkout is on disk, so milestones use only
   flags and maps seen in the reference traces. Turning off the Rocket cameras (event 739) and the
   Blackthorn boulders (1798 to 1800) are left out because the trace alone does not show them to be
   required. The Burned Tower rival milestone (event 1733) reads as a win because the flag stayed
   clear after the lost battle of the first entry. The scripts at the pinned revision would settle
   all three.
3. **Burned Tower start.** The story run's first entry lost the rival battle and blacked out. The
   start is the next entry, after the Pokemon Center. A different policy seed may enter only once.
4. **Decisions are a proxy.** A decision here is a run of the same button. The Red caps count
   assisted commands. The caps and budgets are provisional until the references are replayed
   through a Gen II assisted executor.
5. **Kabuto puzzle screen.** The assisted executor has no puzzle command. Core has
   `pokecore/gen2/puzzles.py`, which reads the board and picks a button.
6. **Blackout.** Blackout is all party HP at zero. A battle the game lets the player lose would also
   end the run. None of the six tasks has one in its reference.
7. **No timing variants.** Each task has one start. Lugia and the other postgame scenes are out of
   scope.

## Red-only harness parts

Each row names where Red is assumed today, the change Gen II needs, and the agent time to do it.
Released code paths stay untouched until the lead starts the Gen II integration. Do them in this
order.

| Order | Part | Where | Change | Agent time |
|---|---|---|---|---|
| 1 | ROM check | `local_setup.py:21`, `local_setup.py:46`, `game.py:66`, `session.py:69`, `cli.py:85`, `cli.py:90` | Accept a Crystal ROM next to Red, keyed by game. `gen2/engine.py:36` already does the Crystal check. `RedEngine` allows only `red` | 45 min |
| 2 | Engine and session load | `game.py:62`, `session.py:28`, `session.py:79`, `session.py:468`, `session.py:559`, `catalog_fixtures.py:30` | A Crystal engine that boots through `gen2/engine.py` and loads every start with its clock lock. Red loads stay as they are | 1.5 h |
| 3 | Fixture pack | `local_setup.py:32`, `local_setup.py:38`, `local_setup.py:97`, `local_setup.py:127`, `local_setup.py:133` | A second pack keyed to the Crystal ROM. `PACKED` gains `initial.clock.json`. The pack dictionary comes from the Crystal ROM | 1 h, then 5 min to build |
| 4 | Game data | `local_setup.py:24`, `local_setup.py:65`, `game_data_tables.py:29`, `game_data_strategy.py:16` | Build Gen II tables from pokecrystal 5beda23f, the pinned revision, or adopt PokeSim's bundle, which is built from it, and pin its hash in `GAME_DATA_SHA256` | 2 h |
| 5 | Evaluators | `milestone_runtime.py:14`, `milestone_runtime.py:23`, `milestone_runtime.py:86`, `catalog_runtime.py:9`, `catalog_runtime.py:68`, `campaign_runtime.py:14`, `navigation_conditions.py:21`, `suite.py:151` | Dispatch Gen II tasks to `gen2/evaluator.py`. The Red no-encounter patch at bank 4 0x7870 has no Crystal twin, so Gen II navigation keeps encounters on | 1 h |
| 6 | Action policy | `action_policy.py:2`, `gameplay_contract.py:6`, `gameplay_commands.py:2`, `gameplay_commands.py:25`, `gameplay_commands.py:37`, `menu_shortcuts.py:4`, `tactical.py:2`, `decision_tasks.py:48` | A Gen II executor for the same commands. Facing, map and position are fixed Red addresses today. Add a puzzle command from `pokecore/gen2/puzzles.py` (gap 5) | 4 h |
| 7 | Text map and screen text | `gameplay.py:51`, `gameplay.py:148`, `gameplay.py:255`, `gameplay.py:356`, `gameplay.py:384`, `dialogue.py:4`, `dialogue.py:5` | The local map from `pokecore/gen2/maps.py` collision, including ice slides. Screen text from `pokecore/gen2/charmap.py` and `screens.py`. The Red tile tables do not apply | 4 h |
| 8 | Prompt text | `gameplay_provider.py:15`, `bounded_provider.py:36`, `providers.py:13`, `compact_provider.py:13` | A separate Crystal prompt with its own checksum. It names Johto and the clock. The Red prompts stay byte for byte | 45 min, then a dry run with the random provider |
| 9 | Calibration | `gen2/catalog.py:27`, `gen2/catalog.json` | Replay each reference through the Gen II executor, recount decisions, and reset caps and budgets (gap 4) | 1 h, then 10 min of emulator time |
| 10 | Catalog and suite | `evaluation_catalog.py:13`, `evaluation_catalog.py:97`, `benchmark_tracks.py:22`, `quick_run.py:21`, `quick_run.py:83`, `catalog_execution.py:25` | Move the six tasks into `catalogs/` under a Gen II category and add them to Short. This is the step that changes Short. Update `tests/fixtures/gen2-prep-released-specs.json` in the same change | 30 min |
| 11 | Replay tiles and colours | `public_site.py:93`, `public_site.py:120`, `public_site.py:253`, `replay_assets/replay.html:13`, `review.py:17`, `screen_motion.py:14` | `sheet_png` already falls back from 2-bit to 8-bit or full colour PNGs, and the player at `replay.html:579` draws whatever the sheet holds. Crystal sheets will be larger, so check the page size. The bezel colours copy the original Game Boy. Place names need the Gen II map table. Motion checks compare luma, which two Crystal colours can share | 1 h |
| 12 | Site | `public_site.py:719`, `catalog_portal.py:112`, `catalog_portal.py:121`, `focused_portal.py:43`, `showcase_assets/index.html:6`, `showcase_assets/index.html:47`, `showcase.py:397` | Text that says Pokemon Red, and a setup command that takes a second ROM | 45 min |

Total: about 18 h of agent work plus about 15 min of build and emulator time.
