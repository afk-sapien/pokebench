# Full-game campaign: 75 milestones and a run profile

This is the scoring definition for one continuous attempt, not 75 separate trials. The runtime scores it as protocol `campaign-progress-v2`. Runs recorded under `campaign-progress-v1` keep their v1 score. See [Versions](#versions).

Champion completion is the primary outcome. The progress score has a 1000-point maximum, with the following breakdown. Optional collection bonuses are not required to pass the game.

| Component | Milestones | Points |
| --- | ---: | ---: |
| Story and quest progress | 20 | 160 |
| Town and League access | 10 | 50 |
| Dungeons and routes | 25 | 200 |
| Gym badges | 8 | 320 |
| Elite Four | 4 | 140 |
| Champion and Hall of Fame | 1 | 80 |
| Capture and team development | 7 | 50 |

## Story and quest progress

Each story milestone is worth 8 points.

- **Choose a starter**: Confirm the starter handover event.
- **Collect Oak's Parcel**: Confirm the parcel receipt event, not mere inventory presence in a supplied save.
- **Deliver Oak's Parcel and receive the Pokedex**: Confirm parcel delivery and Pokedex ownership.
- **Defeat the rival at Nugget Bridge**: Confirm the Cerulean rival victory flag.
- **Help Bill and receive the S.S. Ticket**: Confirm Bill restoration and ticket receipt.
- **Defeat the rival aboard the S.S. Anne**: Confirm the S.S. Anne rival victory flag.
- **Obtain HM01 Cut from the captain**: Confirm the native HM01 reward event.
- **Obtain the Rocket Hideout Lift Key**: Confirm the Lift Key pickup event.
- **Defeat Giovanni in Rocket Hideout**: Confirm the Hideout Giovanni victory flag.
- **Collect the Silph Scope**: Confirm the post-Giovanni Silph Scope pickup.
- **Resolve the ghost Marowak encounter in Pokemon Tower**: Confirm the ghost Marowak completion event.
- **Rescue Mr. Fuji and receive the Poke Flute**: Confirm the rescue and Poke Flute reward events.
- **Clear either sleeping Snorlax roadblock**: Confirm either Route 12 or Route 16 Snorlax removal and resolved encounter. Award once across both locations.
- **Obtain the Silph Co. Card Key**: Confirm the Card Key pickup event.
- **Defeat the rival in Silph Co.**: Confirm the Silph Co. rival victory event.
- **Defeat Giovanni and liberate Silph Co.**: Confirm the Silph Co. Giovanni victory and liberation events.
- **Obtain HM03 Surf in the Safari Zone**: Confirm the native Secret House reward event.
- **Find the Gold Teeth in the Safari Zone**: Confirm the Gold Teeth pickup event even if the item is later handed over.
- **Return the Gold Teeth and receive HM04 Strength**: Confirm the Warden handover and HM04 reward events.
- **Find the Secret Key in Pokemon Mansion**: Confirm the Secret Key pickup event.

## Town and League access

Each town is worth 5 points. Confirm first arrival on the named outdoor map through normal gameplay. Revisits do not earn more points.

Viridian City, Pewter City, Cerulean City, Vermilion City, Lavender Town, Celadon City, Fuchsia City, Saffron City, Cinnabar Island and Indigo Plateau.

## Dungeons and routes

Each milestone is worth 8 points. They show progress through the long stretches between badges. A milestone needs the player on its map outside battle on two checked frames in a row. Where a milestone names a spot, the player must also be inside that box, or within one tile of that point. The drink milestone instead needs any of Fresh Water, Soda Pop or Lemonade in the bag.

| Milestone | Map | Spot |
| --- | ---: | --- |
| Enter Viridian Forest | 51 | |
| Enter Mt. Moon | 59 | |
| Reach the Mt. Moon fossil floor | 61 | near (21, 17) |
| Leave Mt. Moon onto east Route 4 | 15 | x 24 to 89, y 0 to 17 |
| Reach Route 9 | 20 | |
| Enter Rock Tunnel | 82 | |
| Reach Rock Tunnel B1F | 232 | |
| Leave Rock Tunnel onto south Route 10 | 21 | x 0 to 19, y 52 to 71 |
| Enter the west-east Underground Path | 121 | |
| Enter Pokemon Tower | 142 | |
| Get a drink for the Saffron gate guards | | items 60, 61 or 62 |
| Enter the Rocket Hideout | 199 | |
| Reach Rocket Hideout B4F | 202 | |
| Enter Silph Co. | 181 | |
| Reach Silph Co. 7F | 212 | |
| Enter the Safari Zone | 220 | |
| Reach the Safari Zone north area | 218 | |
| Reach the Safari Zone west area | 219 | |
| Enter the Pokemon Mansion | 165 | |
| Reach Pokemon Mansion B1F | 216 | |
| Reach Route 23 | 34 | |
| Enter Victory Road | 108 | |
| Reach Victory Road 2F | 194 | |
| Reach Victory Road 3F | 198 | |
| Leave Victory Road toward Indigo Plateau | 34 | near (14, 31) |

## Gym badges

Each badge is worth 40 points. The evaluator requires the badge bit and the corresponding Gym victory flag.

Boulder (Brock), Cascade (Misty), Thunder (Lt. Surge), Rainbow (Erika), Soul (Koga), Marsh (Sabrina), Volcano (Blaine) and Earth (Giovanni).

## Elite Four

Each victory is worth 35 points: Lorelei, Bruno, Agatha and Lance. The evaluator confirms the corresponding Elite Four victory event.

## Champion and Hall of Fame

- **Defeat the Champion and enter the Hall of Fame**: 80 points. The evaluator requires Champion victory and a new Hall of Fame entry.

## Capture and team development

- **Catch 1 distinct wild species**: 5 points.
- **Catch 5 distinct wild species**: 5 points.
- **Catch 10 distinct wild species**: 5 points.
- **Catch 20 distinct wild species**: 10 points.
- **Evolve a Pokemon for the first time**: 5 points.
- **Evolve Pokemon from 3 distinct evolutionary families**: 10 points.
- **Assemble a party of six distinct species**: 10 points.

Capture counts come from successful wild capture events, including captures sent to the PC. Gifts, trades, evolutions and repeat catches of the same species do not increase them. Two evolutions of the same starter family count as one, and evolution cancellations do not count. The party milestone needs six different species in the party at once through legal acquisitions. It measures roster breadth, not tactical quality.

## Scoring rules

- Champion completion is the primary outcome. Show the 0 to 1000 progress score and its category breakdown alongside it, rather than replacing completion with collection totals.
- Each milestone earns its listed points at most once per attempt. Counts are cumulative thresholds, so 20 distinct wild species earns 25 capture points in total, not 20 points per catch.
- Exclude facts already true at the supplied start. The official campaign starts fresh. No resets, repeated purchases, repeated map visits or repeated easy battles generate extra points.
- Milestone points never decrease. Keep blackouts, item waste and current party condition in the run profile so they explain progress without erasing completed achievements.
- The optional collection component is capped at 50 points. Becoming Champion does not require collecting every bonus, and 1000 points is not required for a full-game pass.
- Award progress from verified game evidence. Do not infer completion from the agent notebook or a claimed tool result. Missing telemetry is unknown, not a zero or an automatic failure.
- Record the first achievement time, frame, decision and cumulative token use. These are 75 observations within one trajectory, not 75 independent trials.
- Publish the score definition to agents before an evaluated run. Keep hidden evaluator state private, and give every model the same scoring rules and budget.

## Versions

- **campaign-progress-v2** (current): adds the 25 dungeon and route milestones. To keep the 1000-point total, it moves weight from the badges (50 to 40 each), the Elite Four (50 to 35 each) and the Champion (200 to 80). Story milestones rise from 5 to 8 points each.
- **campaign-progress-v1**: 50 milestones. The definition is pinned in `src/pokeagent_bench/catalogs/history/campaign-v1.json`. Every run recorded under v1 replays and verifies against that file, so its recorded score never changes.

`scripts/rescore_long.py` replays a stored v1 run's exact inputs, without model calls, and scores the same frames under v2. Every shared milestone must land on its recorded frame, decision, tokens and action count, or the script stops. It writes `campaign-progress-v2.json` beside the run folder. That file is not part of the verified run, and publishing v2 numbers is a separate decision.

## Holistic run profile

### Party strength and readiness

At the start, each badge, League entry and attempt end, save the roster, levels, total and median level, HP/max HP, nonfainted count, status, remaining move PP, Attack, Defense, Speed and Special. Show stat totals as descriptive proxies, not a calibrated battle-power score.

### Moves and team coverage

Show damaging move types with usable PP, status/setup/recovery moves and field moves. Coverage describes available options. It is not a claim that all matchups are winnable.

### Collection and development

Track successful capture events, distinct wild species caught, distinct owned species, evolutions and species held in the party or PC separately. Dex-owned counts include gifts and evolutions, so they are not a substitute for capture counts.

### Battle outcomes and setbacks

Track trainer wins by unique trainer, wild wins, escapes, faints and blackouts separately. Show losses and recoveries at matched progress milestones. Farming wild wins earns no extra score.

### Purchases, item use and money

Record bought and sold quantities by item, purchase spending, sale proceeds, reward income, blackout losses, item use and remaining supplies separately. Report purchases without awarding points for spending. Inventory and money deltas alone must not be called purchases.

### Efficiency at comparable progress

Show cumulative reported tokens with input/output/cache breakdown, decisions, actions, game frames and elapsed time at each milestone. Compare efficiency at the same achieved milestone. Do not count cached input twice or label subscription usage as actual API charges.

## Game evidence sources

- [Red event definitions](https://github.com/pret/pokered/blob/master/constants/event_constants.asm)
- [Red map definitions](https://github.com/pret/pokered/blob/master/constants/map_constants.asm)
